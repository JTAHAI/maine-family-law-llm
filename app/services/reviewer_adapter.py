from __future__ import annotations

from typing import Any

from legal.conversation.human_review_queue import HumanReviewQueueBuilder
from legal.conversation.reviewer_packet import ReviewerPacketBuilder


class ReviewerAdapter:
    def __init__(self) -> None:
        self.queue = HumanReviewQueueBuilder()
        self.packet = ReviewerPacketBuilder()

    def queue_item(self, response: dict[str, Any]) -> dict[str, Any]:
        return self.queue.from_response(response).as_dict()

    def reviewer_packet(self, *, response: dict[str, Any], workflow_id: str, user_prompt: str) -> dict[str, Any]:
        return self.packet.build(response=response, workflow_id=workflow_id, user_prompt=user_prompt)
