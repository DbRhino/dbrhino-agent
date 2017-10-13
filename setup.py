#!/usr/bin/env python
from setuptools import setup

setup(
    name="dbrhino-agent",
    version="0.2.1",
    description="Agent for dbrhino",
    author="Buck Ryan",
    url="https://dbrhino.com",
    classifiers=["Programming Language :: Python :: 3 :: Only"],
    install_requires=[
        "click>=6, <7",
        "requests>=2, <3",
        "PyMySQL<1",
        "psycopg2>=2, <3",
        "jinja2",
        "sqlparse",
        "daemonize",
    ],
    entry_points="""
        [console_scripts]
        dbrhino-agent=dbrhino_agent:cli
    """,
    packages=[
        "dbrhino_agent",
        "dbrhino_agent.db",
    ],
)
