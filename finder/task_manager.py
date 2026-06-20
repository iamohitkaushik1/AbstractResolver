import uuid
import threading
import time
import concurrent.futures
from datetime import datetime
from finder.abstract_fetcher import fetch_full_abstract

def is_incomplete_abstract(abstract):
    if not abstract:
        return True
    text = abstract.strip().lower()
    
    # Common placeholder/truncation indicators (including Unicode ellipses)
    truncation_indicators = [
        "...", 
        "(...)", 
        "[...]", 
        "{...}", 
        "…", 
        "(…)", 
        "[…]", 
        "{…}", 
        "truncated", 
        "abstract truncated",
        "read more",
        "tldr"
    ]
    for indicator in truncation_indicators:
        if indicator in text:
            return True
            
    # Trailing double dots or trailing Unicode ellipsis
    if text.endswith('..') or text.endswith('…'):
        return True
        
    # Short abstracts under 70 characters are placeholder markers
    if len(text) < 70:
        return True
        
    return False

class BackgroundTask:
    def __init__(self, task_id, bib_database, original_filename, config):
        self.task_id = task_id
        self.bib_database = bib_database
        self.original_filename = original_filename
        self.config = config
        
        self.status = "pending"  # pending, running, completed, failed, cancelled
        self.total_entries = len(bib_database.entries) if bib_database else 0
        self.processed_count = 0
        self.success_count = 0
        self.existing_count = 0  # how many already had complete abstracts
        self.failed_count = 0
        self.logs = []
        self.is_cancelled = False
        
        self.lock = threading.RLock()
        self.created_at = datetime.now()
        self.completed_at = None

    def add_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            self.logs.append(f"[{timestamp}] {message}")

    def to_dict(self):
        with self.lock:
            return {
                "task_id": self.task_id,
                "status": self.status,
                "original_filename": self.original_filename,
                "total_entries": self.total_entries,
                "processed_count": self.processed_count,
                "success_count": self.success_count,
                "existing_count": self.existing_count,
                "failed_count": self.failed_count,
                "progress_pct": int((self.processed_count / self.total_entries * 100)) if self.total_entries > 0 else 0,
                "logs": list(self.logs),
                "created_at": self.created_at.isoformat(),
                "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            }

class TaskManager:
    _tasks = {}
    _lock = threading.RLock()

    @classmethod
    def create_task(cls, bib_database, original_filename, config):
        task_id = str(uuid.uuid4())
        task = BackgroundTask(task_id, bib_database, original_filename, config)
        
        with cls._lock:
            cls._tasks[task_id] = task
        
        # Start background thread
        thread = threading.Thread(target=cls._run_task, args=(task,))
        thread.daemon = True
        thread.start()
        
        return task_id

    @classmethod
    def get_task(cls, task_id):
        with cls._lock:
            return cls._tasks.get(task_id)

    @classmethod
    def cancel_task(cls, task_id):
        task = cls.get_task(task_id)
        if task:
            with task.lock:
                task.is_cancelled = True
            task.add_log("Cancellation requested by user...")
            return True
        return False

    @classmethod
    def _run_task(cls, task):
        task.status = "running"
        task.add_log(f"Starting job for {task.original_filename} with {task.total_entries} records.")
        
        try:
            # First, check which ones already have complete abstracts
            # (We only query for entries that are missing abstracts or have incomplete abstracts!)
            pre_existing = 0
            for entry in task.bib_database.entries:
                abs_val = entry.get('abstract')
                has_complete_abs = abs_val and not is_incomplete_abstract(abs_val)
                if has_complete_abs:
                    pre_existing += 1
            task.existing_count = pre_existing
            task.add_log(f"Scan complete. {pre_existing} entries already contain a valid abstract. Skipping DOI-only checks for speed.")
            
            sleep_seconds = task.config.get('sleep_seconds', 1.0)
            
            # Setup list of entries to process
            entries_to_process = []
            for index, entry in enumerate(task.bib_database.entries, 1):
                abs_val = entry.get('abstract')
                has_complete_abs = abs_val and not is_incomplete_abstract(abs_val)
                
                if has_complete_abs:
                    if not entry.get('abstract_source'):
                        entry['abstract_source'] = 'Pre-existing'
                    # Mark processed right away
                    with task.lock:
                        task.processed_count += 1
                    continue
                    
                entries_to_process.append((index, entry))
                
            task.add_log(f"{len(entries_to_process)} entries require abstract resolution lookup.")
            
            if not entries_to_process:
                task.status = "completed"
                task.add_log("Job finished. All abstracts are complete.")
                task.completed_at = datetime.now()
                return

            def process_single_entry(item):
                index, entry = item
                
                # Check cancellation
                if task.is_cancelled:
                    return False
                    
                pid = entry.get('ID', 'Unknown ID')
                title = entry.get('title', '')
                doi = entry.get('doi', '')
                
                task.add_log(f"Processing [{index}/{task.total_entries}] {pid}: {title[:60]}...")
                
                existing_abs = entry.get('abstract')
                has_doi = bool(doi and doi.strip())
                
                reasons = []
                if existing_abs:
                    reasons.append("truncated abstract")
                else:
                    reasons.append("missing abstract")
                if not has_doi:
                    reasons.append("missing DOI")
                task.add_log(f"   [!] Resolving params for {pid}: {', '.join(reasons)}")
                
                def thread_log_callback(msg):
                    task.add_log(f"   [{pid}] {msg.strip()}")
                
                try:
                    abstract, resolved_doi, source, fetch_logs = fetch_full_abstract(doi, title, task.config, log_callback=thread_log_callback)
                    
                    resolved_something = False
                    
                    with task.lock:
                        # 1. Update abstract if resolved
                        if abstract and not is_incomplete_abstract(abstract):
                            entry['abstract'] = abstract
                            entry['abstract_source'] = source
                            resolved_something = True
                            task.add_log(f"   [+] Abstract resolved for {pid} via {source}")
                        else:
                            task.add_log(f"   [-] Failed to resolve full abstract for {pid}.")
                            
                        # 2. Update DOI if resolved and missing
                        if resolved_doi and not has_doi:
                            entry['doi'] = resolved_doi
                            resolved_something = True
                            task.add_log(f"   [+] DOI resolved for {pid}: {resolved_doi} via {source}")
                        elif not has_doi and not resolved_doi:
                            task.add_log(f"   [-] Failed to resolve DOI for {pid}.")
                            
                        if resolved_something:
                            task.success_count += 1
                        else:
                            task.failed_count += 1
                            if fetch_logs:
                                task.add_log(f"       [{pid}] Details:")
                                for flog in fetch_logs:
                                    task.add_log(f"       - {flog}")
                except Exception as e:
                    with task.lock:
                        task.failed_count += 1
                    task.add_log(f"   [-] Error resolving {pid}: {str(e)}")
                
                # Atomically increment progress count
                with task.lock:
                    task.processed_count += 1
                
                # Small courtesy delay between thread items
                time.sleep(sleep_seconds)
                return True

            # Use ThreadPoolExecutor to run tasks in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                # Submit tasks
                futures = [executor.submit(process_single_entry, item) for item in entries_to_process]
                
                # Wait for all to complete or cancellation
                for future in concurrent.futures.as_completed(futures):
                    if task.is_cancelled:
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
            
            if task.is_cancelled:
                task.status = "cancelled"
                task.add_log("Job cancelled by user.")
            else:
                task.status = "completed"
                task.add_log(f"Job finished. Successfully resolved {task.success_count} papers.")
                if task.failed_count > 0:
                    task.add_log(f"{task.failed_count} entries could not be resolved.")
            
        except Exception as e:
            task.status = "failed"
            task.add_log(f"Job failed with critical error: {str(e)}")
        finally:
            task.completed_at = datetime.now()
