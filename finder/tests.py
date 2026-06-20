from django.test import TestCase, Client
from django.urls import reverse
import json
import io
import bibtexparser
from finder.task_manager import TaskManager, BackgroundTask

class AbstractFinderTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.sample_bib = """@article{test_entry,
  author = {Doe, John},
  title = {A study on abstract fetching},
  journal = {Journal of AI Testing},
  year = {2026},
  doi = {10.1000/xyz123}
}"""

    def test_dashboard_load(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Abstract Finder")

    def test_upload_and_status(self):
        # Create a mock file
        mock_file = io.BytesIO(self.sample_bib.encode('utf-8'))
        mock_file.name = "test.bib"

        response = self.client.post(reverse('upload_bib'), {
            'file': mock_file,
            'sleep_seconds': 0.1,
            'max_retries': 1,
            'semantic_scholar_api_key': '',
            'crossref_mailto': 'test@gndu.ac.in',
            'openalex_mailto': 'test@gndu.ac.in',
            'core_api_key': ''
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('task_id', data)
        task_id = data['task_id']

        # Check task exists and can get status
        task = TaskManager.get_task(task_id)
        self.assertIsNotNone(task)
        self.assertEqual(task.original_filename, "test.bib")
        
        # Test status endpoint
        status_response = self.client.get(reverse('task_status', args=[task_id]))
        self.assertEqual(status_response.status_code, 200)
        status_data = status_response.json()
        self.assertEqual(status_data['original_filename'], "test.bib")

    def test_preview_and_edit_and_download(self):
        # Programmatically create a task directly to test preview, editing, and downloading
        parser = bibtexparser.bparser.BibTexParser()
        bib_database = bibtexparser.loads(self.sample_bib, parser=parser)
        
        task_id = "test-task-uuid"
        task = BackgroundTask(task_id, bib_database, "preview_test.bib", {})
        TaskManager._tasks[task_id] = task

        # Get preview
        preview_response = self.client.get(reverse('task_preview', args=[task_id]))
        self.assertEqual(preview_response.status_code, 200)
        preview_data = preview_response.json()
        self.assertEqual(preview_data['total'], 1)
        self.assertEqual(preview_data['entries'][0]['id'], "test_entry")
        self.assertEqual(preview_data['entries'][0]['status'], "missing")

        # Edit abstract
        edit_response = self.client.post(
            reverse('update_entry', args=[task_id]),
            data=json.dumps({
                'entry_id': 'test_entry',
                'abstract': 'This is a manually added abstract for testing that contains enough characters to bypass the short abstract length filter.'
            }),
            content_type='application/json',
            HTTP_X_CSRFTOKEN='dummy_token' # django test client bypasses csrf check by default or we specify
        )
        self.assertEqual(edit_response.status_code, 200)
        self.assertEqual(edit_response.json()['status'], 'success')

        # Re-check preview
        preview_response = self.client.get(reverse('task_preview', args=[task_id]))
        preview_data = preview_response.json()
        self.assertEqual(preview_data['entries'][0]['status'], "edited")
        self.assertEqual(preview_data['entries'][0]['abstract'], 'This is a manually added abstract for testing that contains enough characters to bypass the short abstract length filter.')

        # Download bib
        download_response = self.client.get(reverse('download_bib', args=[task_id]))
        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(download_response['Content-Type'], "application/x-bibtex")
        self.assertIn(b'resolved_preview_test.bib', download_response['Content-Disposition'].encode('utf-8'))
        self.assertIn(b'This is a manually added abstract for testing that contains enough characters to bypass the short abstract length filter.', download_response.content)

    def test_incomplete_abstract_check(self):
        from finder.task_manager import is_incomplete_abstract
        self.assertTrue(is_incomplete_abstract("This is truncated..."))
        self.assertTrue(is_incomplete_abstract("Ends with dot-dot.."))
        self.assertTrue(is_incomplete_abstract("Contains (...) in the middle"))
        self.assertFalse(is_incomplete_abstract("This is a complete abstract with a period that is long enough to pass the length threshold checks."))

        # Test preview with incomplete abstract
        incomplete_bib = """@article{trunc_entry,
  author = {Doe, Jane},
  title = {Truncated study},
  journal = {Journal of Truncation},
  year = {2026},
  abstract = {We present an incomplete abstract ending with...}
}"""
        parser = bibtexparser.bparser.BibTexParser()
        bib_database = bibtexparser.loads(incomplete_bib, parser=parser)
        
        task_id = "test-incomplete-task"
        task = BackgroundTask(task_id, bib_database, "trunc_test.bib", {})
        TaskManager._tasks[task_id] = task

        preview_response = self.client.get(reverse('task_preview', args=[task_id]))
        self.assertEqual(preview_response.status_code, 200)
        preview_data = preview_response.json()
        self.assertEqual(preview_data['entries'][0]['status'], "incomplete")

    def test_csv_upload_and_download(self):
        # 1. Test CSV Upload
        sample_csv = "ID,title,author,journal,year,doi,abstract\npaper_csv_1,A CSV title,Jane Doe,CSV Journal,2026,10.1000/csv123,...\n"
        mock_file = io.BytesIO(sample_csv.encode('utf-8'))
        mock_file.name = "test.csv"

        response = self.client.post(reverse('upload_bib'), {
            'file': mock_file,
            'sleep_seconds': 0.1,
            'max_retries': 1,
            'semantic_scholar_api_key': '',
            'crossref_mailto': 'test@example.com',
            'openalex_mailto': 'test@example.com',
            'core_api_key': ''
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('task_id', data)
        task_id = data['task_id']

        # 2. Test Task Preview for CSV-originated entry
        preview_response = self.client.get(reverse('task_preview', args=[task_id]))
        self.assertEqual(preview_response.status_code, 200)
        preview_data = preview_response.json()
        self.assertEqual(preview_data['total'], 1)
        self.assertEqual(preview_data['entries'][0]['id'], "paper_csv_1")
        self.assertEqual(preview_data['entries'][0]['status'], "incomplete")

        # 3. Test Download CSV
        download_csv_resp = self.client.get(reverse('download_bib', args=[task_id]), {'format': 'csv'})
        self.assertEqual(download_csv_resp.status_code, 200)
        self.assertEqual(download_csv_resp['Content-Type'], "text/csv")
        self.assertIn(b'resolved_test.csv', download_csv_resp['Content-Disposition'].encode('utf-8'))
        self.assertIn(b'paper_csv_1', download_csv_resp.content)
        self.assertIn(b'A CSV title', download_csv_resp.content)

        # 4. Test Download BibTeX (cross-format conversion)
        download_bib_resp = self.client.get(reverse('download_bib', args=[task_id]), {'format': 'bib'})
        self.assertEqual(download_bib_resp.status_code, 200)
        self.assertEqual(download_bib_resp['Content-Type'], "application/x-bibtex")
        self.assertIn(b'resolved_test.bib', download_bib_resp['Content-Disposition'].encode('utf-8'))
        self.assertIn(b'@article{paper_csv_1', download_bib_resp.content)

    def test_latex_title_cleaning(self):
        from finder.abstract_fetcher import clean_latex_title
        self.assertEqual(clean_latex_title("A study on \\textit{Open Source} system"), "A study on Open Source system")
        self.assertEqual(clean_latex_title("{\\beta}-decay in open source"), "beta-decay in open source")
        self.assertEqual(clean_latex_title("A $O(N)$ sorting algorithm"), "A O(N) sorting algorithm")
        self.assertEqual(clean_latex_title("{Curly brackets title}"), "Curly brackets title")

    def test_ris_upload_and_download(self):
        sample_ris = (
            "TY  - JOUR\n"
            "ID  - paper_ris_1\n"
            "TI  - A study on RIS files\n"
            "AU  - Kaushik, Mohit\n"
            "JO  - Journal of RIS Testing\n"
            "PY  - 2026\n"
            "DO  - 10.1000/ris123\n"
            "AB  - An incomplete abstract ending with...\n"
            "ER  - \n"
        )
        mock_file = io.BytesIO(sample_ris.encode('utf-8'))
        mock_file.name = "test.ris"

        response = self.client.post(reverse('upload_bib'), {
            'file': mock_file,
            'sleep_seconds': 0.1,
            'max_retries': 1,
            'semantic_scholar_api_key': '',
            'crossref_mailto': 'test@example.com',
            'openalex_mailto': 'test@example.com',
            'core_api_key': ''
        })

        self.assertEqual(response.status_code, 200)
        task_id = response.json()['task_id']

        # Test preview contains the tldr computed field as well
        preview_response = self.client.get(reverse('task_preview', args=[task_id]))
        self.assertEqual(preview_response.status_code, 200)
        preview_data = preview_response.json()
        self.assertEqual(preview_data['total'], 1)
        self.assertEqual(preview_data['entries'][0]['id'], "paper_ris_1")
        self.assertEqual(preview_data['entries'][0]['status'], "incomplete")
        self.assertEqual(preview_data['entries'][0]['tldr'], "An incomplete abstract ending with.")

        # Test RIS Download
        download_ris_resp = self.client.get(reverse('download_bib', args=[task_id]), {'format': 'ris'})
        self.assertEqual(download_ris_resp.status_code, 200)
        self.assertEqual(download_ris_resp['Content-Type'], "application/x-research-info-systems")
        self.assertIn(b'resolved_test.ris', download_ris_resp['Content-Disposition'].encode('utf-8'))
        self.assertIn(b'ID  - paper_ris_1', download_ris_resp.content)
        self.assertIn(b'TI  - A study on RIS files', download_ris_resp.content)

        # Test cross-conversion download to BibTeX format
        download_bib_resp = self.client.get(reverse('download_bib', args=[task_id]), {'format': 'bib'})
        self.assertEqual(download_bib_resp.status_code, 200)
        self.assertEqual(download_bib_resp['Content-Type'], "application/x-bibtex")
        self.assertIn(b'resolved_test.bib', download_bib_resp['Content-Disposition'].encode('utf-8'))
        self.assertIn(b'@article{paper_ris_1', download_bib_resp.content)
