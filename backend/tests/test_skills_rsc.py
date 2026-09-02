from app.rsc import parse_skills_rsc


def test_parse_skills_rsc() -> None:
    payload = """4:["$","$L2",null,{"componentKey":"com.linkedin.sdui.profile.skill(profile, 1)","children":["$","$Lc",null,{"textProps":{"children":["Technical Writing"]}}]}]
5:["$","$L2",null,{"componentKey":"com.linkedin.sdui.profile.skill(profile, 2)","children":["$","$Lc",null,{"textProps":{"children":["Smart Contracts"]}}]}]"""

    assert parse_skills_rsc(payload) == ["Technical Writing", "Smart Contracts"]
