from abc import ABC

from common.domain.models import GradeStatus


class GradeState(ABC):
    status = None

    def submit(self, submission):
        raise ValueError(
            f"Cannot submit a grade while it is {self.status.value}."
        )

    def approve(self, submission):
        raise ValueError(
            f"Cannot approve a grade while it is {self.status.value}."
        )

    def reject(self, submission, reason):
        raise ValueError(
            f"Cannot reject a grade while it is {self.status.value}."
        )

    def correct(self, submission, new_grade):
        raise ValueError(
            f"Cannot correct a grade while it is {self.status.value}."
        )


class DraftGradeState(GradeState):
    status = GradeStatus.DRAFT

    def submit(self, submission):
        submission.status = GradeStatus.PENDING


class PendingGradeState(GradeState):
    status = GradeStatus.PENDING

    def approve(self, submission):
        submission.status = GradeStatus.SUBMITTED
        submission.rejection_reason = None

    def reject(self, submission, reason):
        submission.status = GradeStatus.REJECTED
        submission.rejection_reason = reason


class RejectedGradeState(GradeState):
    status = GradeStatus.REJECTED

    def correct(self, submission, new_grade):
        submission.grade = new_grade
        submission.status = GradeStatus.DRAFT
        submission.rejection_reason = None


class SubmittedGradeState(GradeState):
    status = GradeStatus.SUBMITTED


GRADE_STATES = {
    GradeStatus.DRAFT: DraftGradeState(),
    GradeStatus.PENDING: PendingGradeState(),
    GradeStatus.REJECTED: RejectedGradeState(),
    GradeStatus.SUBMITTED: SubmittedGradeState(),
}


def get_grade_state(submission):
    return GRADE_STATES[submission.status]
