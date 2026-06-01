from typing import Dict
from datetime import datetime

class AuditPacketGenerator:
    def generate(self, matter_id: str, metadata: Dict) -> Dict:
        return {
            "matter_id": matter_id,
            "generated_at": datetime.utcnow().isoformat(),
            "metadata": metadata,
            "audit_status": "generated"
        }
