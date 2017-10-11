from dbrhino_agent.templates import split


def test_extraction():
    sql = """

  --  here is something...

 grant connect, usage on database {{database}} to {{username}};

 -- that was interesting
 grant all on all to {{username}};grant thatthing on something
     to  -- i think this is weird
 {{username}}
    """
    splitted = split(sql)
    expected = [
        "grant connect, usage on database {{database}} to {{username}};",
        "grant all on all to {{username}};",
        # if the line ends in a comment, the \n is not included in the extract
        # statement...
        "grant thatthing on something\n     to  {{username}}",
    ]
    print("splitted:", splitted)
    print("expected:", expected)
    assert splitted == expected


def test_extraction_empty():
    sql = """

\t
    """
    assert split(sql) == []
