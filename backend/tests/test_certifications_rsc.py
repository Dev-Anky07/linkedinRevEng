from app.rsc import parse_certifications_rsc


def test_parse_certifications_rsc() -> None:
    payload = """0:["$","div",null,{"children":[["$","p",null,{"style":{"color":"x"},"children":["Certification One"]}],["$","p",null,{"children":["Issuer One"]}],"$L1","$L2"]}]
1:["$","$L9",null,{"textProps":{"children":["Issued Sep 2025"]}}]
2:["$","$L9",null,{"textProps":{"children":["Credential ID abc123"]}}]"""

    assert parse_certifications_rsc(payload) == [
        {
            "name": "Certification One",
            "issuer": "Issuer One",
            "issuedDate": "Sep 2025",
            "credentialId": "abc123",
        }
    ]
