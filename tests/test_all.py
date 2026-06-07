import os
import unittest
import datetime
from unittest.mock import patch, MagicMock

from core.config import settings
settings.DATABASE_URL = "postgresql://webdocuser:webdocpassword@localhost:5433/test_bot_db"

def clean_test_db():
    from services.db_service import get_db_connection
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = [row[0] for row in cursor.fetchall()]
        if tables:
            cursor.execute(f"TRUNCATE TABLE {', '.join(tables)} CASCADE")
        conn.commit()
        conn.close()
    except Exception:
        pass

# 2. Imports
from services.db_service import (
    init_db,
    add_application_entry,
    get_applications,
    update_application_entry,
    delete_application_entry,
)
from services.reminder_service import init_scheduler, shutdown_scheduler, get_all_reminders
from core.context import set_context
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from agent.nodes import BotContext, build_llm_context

class MockBot:
    async def send_message(self, *args, **kwargs):
        pass

class TestBuildLlmContext(unittest.TestCase):
    BASE_PROMPT = "You are a test assistant."

    def _build(self, messages):
        ctx = BotContext(messages=messages)
        return build_llm_context(ctx, self.BASE_PROMPT)

    def test_no_messages_returns_hello(self):
        result = self._build([])
        self.assertIsInstance(result[0], SystemMessage)
        self.assertIsInstance(result[1], HumanMessage)
        self.assertEqual(result[1].content, "Hello")

    def test_normal_tool_round_trip(self):
        msgs = [
            HumanMessage(content="hi"),
            AIMessage(content="", tool_calls=[{"id": "tc_1", "name": "foo", "args": {}}]),
            ToolMessage(content="result", tool_call_id="tc_1"),
            AIMessage(content="done"),
        ]
        result = self._build(msgs)
        ai_with_tools = [m for m in result if isinstance(m, AIMessage) and m.tool_calls]
        self.assertEqual(len(ai_with_tools), 1)
        tool_msgs = [m for m in result if isinstance(m, ToolMessage)]
        self.assertEqual(len(tool_msgs), 1)

    def test_orphaned_tool_calls_are_stripped(self):
        msgs = [
            HumanMessage(content="hello"),
            AIMessage(content="thinking...", tool_calls=[{"id": "tc_99", "name": "bar", "args": {}}]),
            HumanMessage(content="next question"),
            AIMessage(content="sure"),
        ]
        result = self._build(msgs)
        for m in result:
            if isinstance(m, AIMessage):
                if m.tool_calls:
                    self.fail(f"Found AIMessage with orphaned tool_calls: {m.tool_calls}")

    def test_trailing_ai_with_tool_calls_sanitized(self):
        msgs = [
            HumanMessage(content="do something"),
            AIMessage(content="", tool_calls=[{"id": "tc_end", "name": "baz", "args": {}}]),
        ]
        result = self._build(msgs)
        for m in result:
            if isinstance(m, AIMessage) and m.tool_calls:
                tc_ids = {tc["id"] for tc in m.tool_calls}
                tm_ids = {m2.tool_call_id for m2 in result if isinstance(m2, ToolMessage)}
                self.assertTrue(tc_ids.issubset(tm_ids), f"Orphaned tool_calls found: {tc_ids}")

    def test_empty_tool_calls_list_not_sent(self):
        msgs = [
            HumanMessage(content="start"),
            AIMessage(content="plan", tool_calls=[{"id": "tc_gone", "name": "x", "args": {}}]),
            HumanMessage(content="continue"),
            AIMessage(content="ok"),
        ]
        result = self._build(msgs)
        for m in result:
            if isinstance(m, AIMessage) and hasattr(m, "tool_calls"):
                if m.tool_calls == []:
                    pass
                elif m.tool_calls:
                    tc_ids = {tc["id"] for tc in m.tool_calls}
                    tm_ids = {m2.tool_call_id for m2 in result if isinstance(m2, ToolMessage)}
                    self.assertTrue(tc_ids.issubset(tm_ids), f"tool_calls {tc_ids} without matching ToolMessages {tm_ids}")

    def test_get_supervisor_system_prompt_with_profile(self):
        from agent.prompts import get_supervisor_system_prompt
        profile = {
            "current_role": "Senior Software Developer",
            "experience_years": 4,
            "skills": ["Python", "Django", "FastAPI"]
        }
        prompt = get_supervisor_system_prompt("AVAILABLE", profile)
        self.assertIn("Senior Software Developer", prompt)
        self.assertIn("4 years", prompt)
        self.assertIn("Python, Django, FastAPI", prompt)

class TestJobApplicationsUpdate(unittest.TestCase):
    def setUp(self):
        init_db()
        clean_test_db()

    def tearDown(self):
        clean_test_db()

    def test_update_application_db(self):
        msg = add_application_entry(
            company="Unknown Inc",
            position="Python Developer",
            email="jobs@unknown.com",
            status="Applied",
            notes="Initial notes",
        )
        self.assertIn("Added to DB", msg)

        apps = get_applications()
        self.assertEqual(len(apps), 1)
        app = apps[0]
        app_id = app["id"]
        self.assertEqual(app["Company"], "Unknown Inc")
        self.assertEqual(app["Position"], "Python Developer")

        success = update_application_entry(
            app_id=app_id,
            company="Meritto",
            status="Interviewing",
            notes="Updated notes",
        )
        self.assertTrue(success)

        apps = get_applications()
        self.assertEqual(len(apps), 1)
        updated_app = apps[0]
        self.assertEqual(updated_app["Company"], "Meritto")
        self.assertEqual(updated_app["Position"], "Python Developer")
        self.assertEqual(updated_app["Status"], "Interviewing")
        self.assertEqual(updated_app["Notes"], "Updated notes")

        success = update_application_entry(
            old_company="Meritto",
            old_position="Python Developer",
            position="Senior Python Developer",
        )
        self.assertTrue(success)

        apps = get_applications()
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]["Position"], "Senior Python Developer")

    def test_update_tool_action(self):
        from agent.tools import manage_job_applications_tool
        add_res = manage_job_applications_tool.invoke({
            "action": "add",
            "company": "Placeholder Co",
            "position": "Software Engineer",
            "notes": "TBD",
        })
        self.assertIn("Added to DB", add_res)

        list_res_initial = manage_job_applications_tool.invoke({"action": "list"})
        self.assertIn("Placeholder Co - Software Engineer (Pending)", list_res_initial)

        update_res = manage_job_applications_tool.invoke({
            "action": "update",
            "old_company": "Placeholder Co",
            "old_position": "Software Engineer",
            "company": "Meritto",
        })
        self.assertEqual(update_res, "Application updated successfully.")

        list_res = manage_job_applications_tool.invoke({"action": "list"})
        self.assertIn("Meritto - Software Engineer", list_res)
        self.assertNotIn("Placeholder Co", list_res)

        update_res2 = manage_job_applications_tool.invoke({
            "action": "update",
            "app_id": 1,
            "status": "Offer",
            "notes": "Got the offer!",
        })
        self.assertEqual(update_res2, "Application updated successfully.")

        list_res2 = manage_job_applications_tool.invoke({"action": "list"})
        self.assertIn("Meritto - Software Engineer (Offer)", list_res2)

        delete_res = manage_job_applications_tool.invoke({"action": "delete", "app_id": 1})
        self.assertEqual(delete_res, "Application deleted.")

        list_res3 = manage_job_applications_tool.invoke({"action": "list"})
        self.assertIn("No applications found", list_res3)

    def test_system_reset_tool(self):
        from agent.tools import reset_user_data_tool
        result = reset_user_data_tool.invoke({})
        self.assertIn("reset", result.lower())

    def test_url_handling(self):
        add_application_entry(
            company="URL Tech",
            position="Engineer",
            email="tech@url.com",
            status="Pending",
            notes="Has url",
            url="https://urltech.jobs/123",
        )
        
        apps = get_applications()
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]["URL"], "https://urltech.jobs/123")

        success = update_application_entry(
            app_id=apps[0]["id"],
            url="https://urltech.jobs/456",
        )
        self.assertTrue(success)

        apps = get_applications()
        self.assertEqual(apps[0]["URL"], "https://urltech.jobs/456")

        from agent.tools import manage_job_applications_tool
        tool_res = manage_job_applications_tool.invoke({
            "action": "list"
        })
        self.assertIn("[URL: https://urltech.jobs/456]", tool_res)

    @patch("agent.tools.send_gmail_message")
    def test_final_send_email_auto_track(self, mock_send):
        mock_send.return_value = "Email sent successfully."

        add_application_entry(
            company="Duplicate Prevention Co",
            position="Developer",
            status="Pending",
        )

        from agent.tools import final_send_email_do_not_call
        res = final_send_email_do_not_call.invoke({
            "recruiter_email": "recruiter@dup.com",
            "subject": "App",
            "body": "Body",
            "company_name": "Duplicate Prevention Co",
            "position": "Developer",
        })

        self.assertIn("Tracker updated", res)
        
        apps = get_applications()
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]["Status"], "Applied")
        self.assertEqual(apps[0]["Email"], "recruiter@dup.com")

        import datetime
        today_str = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        self.assertEqual(apps[0]["Date Applied"], today_str)

class TestUserProfileAndCoverLetterEndpoints(unittest.TestCase):
    def setUp(self):
        init_db()
        clean_test_db()

    def tearDown(self):
        clean_test_db()

    def test_cover_letter_endpoints(self):
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)

        from services.db_service import clear_resume_table, save_resume_entry
        clear_resume_table()

        res = client.get("/api/user/cover-letter")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"cover_letter": ""})

        save_resume_entry("/path/to/res", "resume.pdf", "resume text", "original cl text")

        res = client.get("/api/user/cover-letter")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"cover_letter": "original cl text"})

        res = client.put("/api/user/cover-letter", json={"cover_letter": "updated cl text"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"success": True})

        res = client.get("/api/user/cover-letter")
        self.assertEqual(res.json(), {"cover_letter": "updated cl text"})

    def test_user_profile_endpoints(self):
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)

        from services.user_profile_service import delete_all_profile_files
        delete_all_profile_files()

        res = client.get("/api/user/profile")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {})

        profile_data = {
            "current_role": "Senior Engineer",
            "experience_level": "senior",
            "experience_years": 5,
            "skills": ["Python", "FastAPI"],
            "industry": "Software Engineering",
            "domain": "Backend",
            "example_type": "code"
        }
        res = client.put("/api/user/profile", json=profile_data)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"success": True})

        res = client.get("/api/user/profile")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["current_role"], "Senior Engineer")

class TestAgentTools(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        init_db()
        clean_test_db()
        init_scheduler(MockBot())
        set_context(chat_id=456, bot_instance=MockBot())

    async def asyncTearDown(self):
        shutdown_scheduler()
        clean_test_db()

    @patch("services.resume_service.generate_cover_letter_content")
    @patch("services.resume_service.extract_user_profile")
    async def test_save_resume(self, mock_profile, mock_cl):
        mock_profile.return_value = None
        mock_cl.return_value = "Cover Letter content"
        from services.resume_service import save_resume
        resume_content = b"Skills: Python, FastAPI. Experience: 3 years."
        res = await save_resume(resume_content, "test_resume.txt")
        path = res["file_path"]
        self.assertTrue(os.path.exists(path))
        if os.path.exists(path):
            os.remove(path)

    @patch("services.learning_service.generate_learning_path")
    async def test_learning_service(self, mock_gen):
        mock_gen.return_value = True
        from services.db_service import add_topic, get_topics
        topic_id = add_topic("Python Decorators", "micro")
        topics = get_topics()
        test_topic = next((t for t in topics if t["id"] == topic_id), None)
        self.assertIsNotNone(test_topic)
        self.assertEqual(test_topic["type"], "micro")

    @patch("services.resume_service.get_resume_entry")
    @patch("services.resume_service.analyze_skill_gap")
    async def test_skill_gap_service(self, mock_gap, mock_resume):
        mock_resume.return_value = {"resume_text": "Python Developer"}
        mock_gap.return_value = "Missing Kubernetes."
        from services.resume_service import analyze_skill_gap
        res = await analyze_skill_gap("Need Kubernetes.")
        self.assertEqual(res, "Missing Kubernetes.")

    @patch("agent.tools.process_workout_log")
    async def test_manage_workouts_tool(self, mock_process):
        mock_process.return_value = "Bench Press logged."
        from agent.tools import manage_workouts_tool
        res = await manage_workouts_tool.ainvoke({"action": "add", "content": "Bench 100kg 3x5"})
        self.assertEqual(res, "Bench Press logged.")
        res_list = await manage_workouts_tool.ainvoke({"action": "list", "date": "01-01-2026"})
        self.assertIn("No workouts logged", res_list)
        res_cat = await manage_workouts_tool.ainvoke({"action": "categories"})
        self.assertIn("No exercises found", res_cat)
        res_del = await manage_workouts_tool.ainvoke({"action": "delete", "id": 1, "date": "01-01-2026"})
        self.assertIn("not found", res_del)

    async def test_manage_dumps_tool(self):
        from agent.tools import manage_dumps_tool
        res = await manage_dumps_tool.ainvoke({"action": "add", "content": "My new idea"})
        self.assertIn("saved", res.lower())
        res_list = await manage_dumps_tool.ainvoke({"action": "list"})
        self.assertIn("Brain Dump Items", res_list)
        res_del = await manage_dumps_tool.ainvoke({"action": "delete", "id": 1})
        self.assertIn("deleted", res_del.lower())

    @patch("agent.tools.get_current_chat_id")
    @patch("agent.tools.add_reminder")
    async def test_manage_reminders_tool(self, mock_add, mock_chat_id):
        mock_chat_id.return_value = 123
        mock_add.return_value = ("job_1", datetime.datetime(2026, 6, 6, 12, 0))
        from agent.tools import manage_reminders_tool
        res = await manage_reminders_tool.ainvoke({"action": "add", "message": "Buy milk", "target_epoch": 1780747680.0})
        self.assertIn("Reminder set", res)
        res_list = await manage_reminders_tool.ainvoke({"action": "list"})
        self.assertIn("No pending", res_list)

    @patch("agent.tools.get_current_chat_id")
    @patch("agent.tools.add_recurring_reminder")
    @patch("agent.tools.get_all_reminders")
    @patch("agent.tools.scheduler")
    async def test_manage_cron_tool(self, mock_scheduler, mock_get_all, mock_add, mock_chat_id):
        mock_chat_id.return_value = 123
        mock_add.return_value = ("cron_job_1", "every 60 minutes")
        mock_get_all.return_value = [{
            "id": "cron_job_1",
            "type": "recurring",
            "message": "Hourly check",
            "schedule": "every 60 minutes",
            "is_agent": False,
            "next_run_time": None
        }]
        mock_scheduler.get_job.return_value = None
        from agent.tools import manage_cron_tool
        res = await manage_cron_tool.ainvoke({"action": "add", "message": "Hourly check", "interval_minutes": 60})
        self.assertIn("Scheduled recurring reminder", res)
        res_list = await manage_cron_tool.ainvoke({"action": "list"})
        self.assertIn("Recurring Tasks", res_list)

    @patch("agent.tools.analyze_company_reviews")
    async def test_get_company_reviews_tool(self, mock_analyze):
        mock_analyze.return_value = "Great work life balance."
        from agent.tools import get_company_reviews_tool
        res = await get_company_reviews_tool.ainvoke({"company_name": "Google"})
        self.assertEqual(res, "Great work life balance.")

    @patch("tavily.TavilyClient")
    async def test_web_search_tool(self, mock_tavily):
        mock_instance = MagicMock()
        mock_instance.search.return_value = {
            "results": [{"title": "Python 3.12", "url": "https://python.org", "content": "FastAPI is cool."}],
            "answer": "FastAPI is cool"
        }
        mock_tavily.return_value = mock_instance
        from agent.tools import web_search_tool
        res = await web_search_tool.ainvoke({"query": "FastAPI"})
        self.assertIn("Python 3.12", res)

    @patch("services.db_service.get_resume_entry")
    def test_list_my_resumes_tool(self, mock_get_resume):
        mock_get_resume.return_value = {
            "file_name": "resume.pdf",
            "created_at": "2026-06-06 12:00:00"
        }
        from agent.tools import list_my_resumes_tool
        res = list_my_resumes_tool.invoke({})
        self.assertIn("resume.pdf", res)

    @patch("agent.tools.analyze_skill_gap")
    async def test_analyze_missing_skills_tool(self, mock_analyze):
        mock_analyze.return_value = "Missing Django."
        from agent.tools import analyze_missing_skills_tool
        res = await analyze_missing_skills_tool.ainvoke({"job_description": "We need Python and Django."})
        self.assertIn("Missing Django", res)

    @patch("services.db_service.get_resume_entry")
    @patch("agent.tools.get_llm")
    async def test_draft_email_tool(self, mock_get_llm, mock_get_resume):
        mock_get_resume.return_value = {
            "resume_text": "Experienced Dev",
            "cover_letter_text": "Generic CL"
        }
        mock_llm = MagicMock()
        mock_structured_llm = MagicMock()
        async def mock_ainvoke(*args, **kwargs):
            mock_draft = MagicMock()
            mock_draft.subject = "Custom CL Subject"
            mock_draft.body = "Custom CL Body"
            return mock_draft
        mock_structured_llm.ainvoke = mock_ainvoke
        mock_llm.with_structured_output.return_value = mock_structured_llm
        mock_get_llm.return_value = mock_llm

        from agent.tools import draft_email_tool
        res = await draft_email_tool.ainvoke({
            "recipient_email": "jobs@test.com",
            "is_job_application": True,
            "company_name": "Test Co",
            "role_name": "Developer"
        })
        self.assertIn("Custom CL Body", res)
        res_generic = await draft_email_tool.ainvoke({
            "recipient_email": "friend@test.com",
            "subject": "Hello",
            "body": "Hi there"
        })
        self.assertIn("Hi there", res_generic)

    @patch("agent.tools.send_gmail_message")
    def test_final_send_email_do_not_call(self, mock_send):
        mock_send.return_value = "Email sent successfully."
        from agent.tools import final_send_email_do_not_call
        res = final_send_email_do_not_call.invoke({
            "recruiter_email": "recruiter@comp.com",
            "subject": "Hello",
            "body": "Body",
            "company_name": "Test Co",
            "position": "Dev"
        })
        self.assertTrue("Added to DB" in res or "Tracker updated" in res)

    def test_reset_user_data_tool(self):
        from agent.tools import reset_user_data_tool
        res = reset_user_data_tool.invoke({})
        self.assertIn("reset", res.lower())

    def test_manage_todos_tool(self):
        from agent.tools import manage_todos_tool
        res = manage_todos_tool.invoke({"action": "add", "task": "Learn unit tests"})
        self.assertIn("added", res.lower())
        res_list = manage_todos_tool.invoke({"action": "list"})
        self.assertIn("Learn unit tests", res_list)

    def test_manage_job_applications_tool(self):
        from agent.tools import manage_job_applications_tool
        res = manage_job_applications_tool.invoke({"action": "add", "company": "Apple", "position": "Senior Dev"})
        self.assertIn("Added to DB", res)
        res_list = manage_job_applications_tool.invoke({"action": "list"})
        self.assertIn("Apple - Senior Dev", res_list)

    def test_manage_bookmarks_tool(self):
        from agent.tools import manage_bookmarks_tool
        res = manage_bookmarks_tool.invoke({"action": "add", "url": "https://google.com", "title": "Google"})
        self.assertIn("saved", res.lower())
        res_list = manage_bookmarks_tool.invoke({"action": "list"})
        self.assertIn("google.com", res_list)

    @patch("agent.tools.classify_topic")
    @patch("agent.tools.generate_learning_path")
    @patch("agent.tools.get_current_lesson")
    async def test_manage_learning_tool(self, mock_lesson, mock_gen, mock_classify):
        mock_classify.return_value = "main"
        mock_gen.return_value = True
        mock_lesson.return_value = {"id": 1, "title": "Intro to Go"}
        from agent.tools import manage_learning_tool
        res = await manage_learning_tool.ainvoke({"action": "add", "topic": "Go Programming"})
        self.assertIn("added", res.lower())
        res_list = await manage_learning_tool.ainvoke({"action": "status"})
        self.assertIn("Intro to Go", res_list)

    @patch("agent.tools.parse_finance_entries")
    def test_manage_finance_tool(self, mock_parse):
        from services.db_service import get_finance_categories
        cats = get_finance_categories()
        food_cat = next(c for c in cats if "food" in c["name"].lower())
        mock_parse.return_value = [{"category_id": food_cat["id"], "amount": 15.0, "description": "Coffee"}]
        
        from agent.tools import manage_finance_tool
        res = manage_finance_tool.invoke({"action": "add_transaction", "expense_text": "Coffee 15"})
        self.assertIn("Coffee", res)
        res_list = manage_finance_tool.invoke({"action": "list_transactions"})
        self.assertIn("Coffee", res_list)

    @patch("agent.tools.parse_food_entry")
    def test_manage_nutrition_tool(self, mock_parse):
        mock_parse.return_value = [{
            "name": "banana",
            "quantity": "1",
            "calories": 105,
            "protein": 1.3,
            "carbs": 27.0,
            "fat": 0.3
        }]
        from agent.tools import manage_nutrition_tool
        res = manage_nutrition_tool.invoke({"action": "log", "food_text": "One banana"})
        self.assertIn("Logged", res)
        res_list = manage_nutrition_tool.invoke({"action": "get_macros"})
        self.assertIn("banana", res_list)

    def test_manage_facts_tool(self):
        from agent.tools import manage_facts_tool
        res = manage_facts_tool.invoke({"action": "add", "fact_text": "He prefers Python"})
        self.assertIn("remembered", res.lower())
        res_list = manage_facts_tool.invoke({"action": "list"})
        self.assertIn("He prefers Python", res_list)

    @patch("services.calendar_service.list_calendar_events")
    async def test_manage_calendar_tool(self, mock_list):
        mock_list.return_value = [{"id": "ev_1", "summary": "Meeting", "start": {"dateTime": "2026-06-06T10:00:00"}}]
        from agent.tools import manage_calendar_tool
        res = await manage_calendar_tool.ainvoke({"action": "list"})
        self.assertIn("Meeting", res)

    @patch("services.job_scraper_service.trigger_job_scraper")
    async def test_manage_job_scraper_tool(self, mock_trigger):
        mock_trigger.return_value = True
        from agent.tools import manage_job_scraper_tool
        res = await manage_job_scraper_tool.ainvoke({"action": "run", "keywords": ["Python"]})
        self.assertIn("triggered successfully", res)

    @patch("services.resume_service.delete_all_resumes")
    @patch("services.user_profile_service.delete_all_profile_files")
    async def test_clear_user_data_tool(self, mock_profile, mock_resumes):
        from agent.tools import clear_user_data_tool
        res = await clear_user_data_tool.ainvoke({"confirmation": "YES"})
        self.assertIn("All user data has been cleared", res)
