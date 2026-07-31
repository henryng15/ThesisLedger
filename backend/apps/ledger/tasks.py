"""Celery tasks for background analysis processing.

Tasks run in worker processes and interact with the database through
the services module. The main task is run_analysis_task which executes
the full LangGraph pipeline for a thesis.
"""

import logging

from celery import shared_task
from django.conf import settings

from apps.ledger.models import AnalysisJob
from apps.ledger.services import fail_job, run_mock_analysis, run_real_analysis

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30, ignore_result=True)
def run_analysis_task(self, job_id: str) -> dict:
    """Execute analysis for a job.

    This task is enqueued when a user submits a thesis for analysis.
    It runs the LangGraph pipeline (or mock for now) and updates the
    job status as it progresses.

    Args:
        job_id: UUID of the AnalysisJob to process

    Returns:
        Dict with job_id and final status
    """
    logger.info(f"Starting analysis task for job {job_id}")

    try:
        job = AnalysisJob.objects.select_related("thesis__company").get(id=job_id)
    except AnalysisJob.DoesNotExist:
        logger.error(f"Job {job_id} not found")
        return {"job_id": job_id, "status": "not_found"}

    # Store Celery task ID for tracking
    job.celery_task_id = self.request.id or ""
    job.save(update_fields=["celery_task_id", "updated_at"])

    try:
        # Use real analysis if configured, otherwise mock
        use_real = getattr(settings, "USE_REAL_ANALYSIS", False)
        if use_real:
            logger.info(f"Running real LangGraph analysis for job {job_id}")
            run_real_analysis(job)
        else:
            logger.info(f"Running mock analysis for job {job_id}")
            run_mock_analysis(job)

        logger.info(f"Completed analysis for job {job_id}")
        return {"job_id": job_id, "status": job.status}

    except Exception as exc:
        logger.exception(f"Analysis failed for job {job_id}")
        fail_job(job, str(exc))

        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        return {"job_id": job_id, "status": "failed", "error": str(exc)}
