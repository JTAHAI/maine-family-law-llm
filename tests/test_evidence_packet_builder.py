from legal.evidence.evidence_packet_builder import EvidencePacketBuilder

def test_evidence_packet_builder():
    builder = EvidencePacketBuilder()

    packet = builder.build(
        matter_id="matter-1",
        timeline=[{"event":"filing"}],
        evidence_map=[{"fact":"support unpaid"}],
        authorities=[]
    )

    assert packet.matter_id == "matter-1"
