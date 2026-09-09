import threading
import queue
import time
from database import get_job, update_job


_job_queue = queue.Queue()
_worker_thread = None
_stop_event = threading.Event()
_current_job_id = None
_lock = threading.Lock()


def enqueue_job(job_id, user_id, channel):
    _job_queue.put((job_id, user_id, channel))
    print(f"[QUEUE] Job {job_id} enqueued")


def get_current_job():
    with _lock:
        return _current_job_id


def stop_current_job():
    _stop_event.set()


def is_stop_requested():
    return _stop_event.is_set()


def clear_stop():
    _stop_event.clear()


def start_worker():
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    _worker_thread.start()
    print("[QUEUE] Worker started")


def _worker_loop():
    from worker import process_job
    print("[QUEUE] Worker loop running")
    while True:
        try:
            job_id, user_id, channel = _job_queue.get(timeout=5)
        except queue.Empty:
            continue
        with _lock:
            global _current_job_id
            _current_job_id = job_id
            clear_stop()
        try:
            process_job(job_id, user_id, channel)
        except Exception as e:
            print(f"[QUEUE] Error processing job {job_id}: {e}")
            update_job(job_id, status="failed", error_message=str(e))
        finally:
            with _lock:
                _current_job_id = None
            _job_queue.task_done()


def get_queue_size():
    return _job_queue.qsize()
