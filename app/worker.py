import multiprocessing
import time
from typing import Callable, Dict, Any
from .job_manager import job_manager

class Worker:
    def __init__(self):
        self.job_handlers: Dict[str, Callable] = {}
        self._process = None

    def register_handler(self, job_type: str, handler: Callable):
        """Register a handler function for a specific job type"""
        self.job_handlers[job_type] = handler

    def start(self):
        """Start the worker process"""
        if self._process is None or not self._process.is_alive():
            self._process = multiprocessing.Process(target=self._run)
            self._process.start()

    def stop(self):
        """Stop the worker process"""
        if self._process and self._process.is_alive():
            self._process.terminate()
            self._process.join()

    def _run(self):
        """Main worker loop"""
        while True:
            # Check for pending jobs
            for job_id, job in job_manager.jobs.items():
                if job.status == "pending":
                    handler = self.job_handlers.get(job.type)
                    if handler:
                        try:
                            # Update status to processing
                            job_manager.update_job_status(job_id, "processing")
                            
                            # Execute the handler
                            result = handler(**job.params)
                            
                            # Update status to completed with result
                            job_manager.update_job_status(job_id, "completed", result=result)
                        except Exception as e:
                            # Update status to failed with error
                            job_manager.update_job_status(job_id, "failed", error=str(e))
            
            # Sleep briefly to prevent CPU thrashing
            time.sleep(1)

# Example handler for audio generation
def audio_generation_handler(email_id: str, **kwargs) -> str:
    """
    Example handler for audio generation jobs
    Returns the path to the generated audio file
    """
    # This is where you'd put your actual audio generation logic
    # For now, we'll just simulate a long-running process
    time.sleep(5)  # Simulate work
    return f"generated_audio_{email_id}.mp3"

# Create global worker instance
worker = Worker()

# Register handlers
worker.register_handler("generate_audio", audio_generation_handler)

# Start worker process when the application starts
def init_worker():
    worker.start() 