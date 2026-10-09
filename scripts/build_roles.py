"""Build data/roles.json, data/skill_aliases.json and data/resources.json from the curated tables below.

    python scripts/build_roles.py            write the three files
    python scripts/build_roles.py --check    validate the tables and print the demo-CV match without writing

The skill lists are derived from the public ESCO and O*NET occupational taxonomies plus a review of
public job postings for the Pakistani graduate market; they are curated by hand, not scraped. Every
skill has one canonical spelling shared by every role, so exact-name matching in the matcher works
across roles, jobs and CVs. Weights follow docs/data_formats.md: core = 3, preferred = 1.

Resources are free links only, from: freeCodeCamp, Kaggle Learn, MIT OpenCourseWare, Google Skillshop,
Khan Academy, Microsoft Learn, AWS Skill Builder (free tier), The Odin Project, CS50 and the official
documentation of each tool or language. Deep links are used only where they are well established;
otherwise the well-known landing page is given.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"

WEIGHTS = {"core": 3, "preferred": 1}
CATEGORY_NAMES = {"language", "tool", "framework", "soft_skill", "domain"}

# The demo persona's CV (see the team brief). Only exact names count, as in matcher.match.
DEMO_CV_SKILLS = [
    "Python", "Pandas", "NumPy", "Matplotlib", "Jupyter", "Excel", "Statistics", "Git",
    "Communication", "Teamwork", "Kubernetes", "Docker",
]
DEMO_ROLE = "Data Analyst"
DEMO_MATCH_RANGE = (50.0, 70.0)

# --------------------------------------------------------------------------- skill categories

_LANGUAGES = [
    "Python", "SQL", "JavaScript", "TypeScript", "Java", "C", "C++", "C#", "Go", "Kotlin", "Swift",
    "Dart", "R", "Bash", "HTML", "CSS", "PowerShell", "DAX",
]
_TOOLS = [
    "Excel", "Tableau", "Power BI", "Looker Studio", "Git", "Docker", "Kubernetes", "AWS", "Azure",
    "Google Cloud", "Jupyter", "Jira", "Confluence", "Trello", "Linux", "Terraform", "Ansible",
    "Jenkins", "GitHub Actions", "Postman", "Selenium", "Figma", "Adobe XD", "Adobe Photoshop",
    "Canva", "Google Analytics", "Google Ads", "Google Search Console", "WordPress", "Mailchimp",
    "Wireshark", "Nmap", "Burp Suite", "Metasploit", "Splunk", "Kali Linux", "MATLAB",
    "Android Studio", "Xcode", "Apache Airflow", "Apache Spark", "Apache Kafka", "Redis", "MongoDB",
    "PostgreSQL", "MySQL", "SQL Server", "Oracle Database", "Firebase", "Nginx", "Prometheus",
    "Grafana", "Active Directory", "Windows Server", "Microsoft Office", "Microsoft Project",
    "Hugging Face", "MLflow", "Arduino", "Raspberry Pi", "KiCad", "dbt", "Snowflake", "BigQuery",
    "Elasticsearch", "Cisco IOS", "Markdown",
]
_FRAMEWORKS = [
    "React", "Angular", "Vue.js", "Node.js", "Express.js", "Next.js", "Django", "Flask", "FastAPI",
    "Spring Boot", ".NET", "Flutter", "React Native", "Tailwind CSS", "Bootstrap", "Pandas", "NumPy",
    "Matplotlib", "Seaborn", "scikit-learn", "TensorFlow", "PyTorch", "Keras", "OpenCV", "LangChain",
    "Jest", "pytest", "JUnit", "Cypress", "Playwright", "FreeRTOS",
]
_SOFT_SKILLS = [
    "Communication", "Problem Solving", "Teamwork", "Critical Thinking", "Time Management",
    "Presentation Skills", "Leadership", "Attention to Detail", "Adaptability", "Negotiation",
    "Creativity", "Empathy", "Writing",
]
_DOMAINS = [
    "Statistics", "Data Visualization", "Data Cleaning", "A/B Testing", "Machine Learning",
    "Deep Learning", "Natural Language Processing", "Computer Vision", "Data Modeling", "ETL",
    "Data Warehousing", "Big Data", "Feature Engineering", "MLOps", "Large Language Models",
    "Prompt Engineering", "Generative AI", "Linear Algebra", "Business Analysis",
    "Requirements Gathering", "Agile", "Scrum", "Software Testing", "Test Automation", "REST APIs",
    "System Design", "Data Structures and Algorithms", "Object-Oriented Programming", "Microservices",
    "Networking", "Routing and Switching", "Firewalls", "Network Security", "Penetration Testing",
    "Vulnerability Assessment", "Incident Response", "Cryptography", "Cloud Computing", "CI/CD",
    "Infrastructure as Code", "Monitoring", "Responsive Design", "Web Accessibility",
    "User Research", "Wireframing", "Prototyping", "Usability Testing", "Visual Design",
    "Design Systems", "SEO", "Content Marketing", "Social Media Marketing", "Email Marketing",
    "Copywriting", "Market Research", "Technical Documentation", "API Documentation",
    "Financial Modeling", "Accounting", "Financial Analysis", "Valuation", "Forecasting",
    "Budgeting", "Microcontrollers", "RTOS", "PCB Design", "Signal Processing", "IoT",
    "Circuit Design", "Product Strategy", "Product Roadmapping", "Stakeholder Management",
    "Project Planning", "Risk Management", "Database Design", "Backup and Recovery",
    "Performance Tuning", "Troubleshooting", "Hardware Support", "Customer Service",
]

CATEGORIES: dict[str, str] = {
    **{name: "language" for name in _LANGUAGES},
    **{name: "tool" for name in _TOOLS},
    **{name: "framework" for name in _FRAMEWORKS},
    **{name: "soft_skill" for name in _SOFT_SKILLS},
    **{name: "domain" for name in _DOMAINS},
}

# --------------------------------------------------------------------------- roles

# (role name, core skills, preferred skills). Order within a list is the display order.
ROLES: list[tuple[str, list[str], list[str]]] = [
    (
        "Data Analyst",
        ["SQL", "Excel", "Python", "Statistics", "Data Visualization", "Pandas", "Communication"],
        ["Tableau", "Power BI", "NumPy", "Jupyter", "Git", "Data Cleaning", "Problem Solving",
         "Presentation Skills", "A/B Testing"],
    ),
    (
        "Data Scientist",
        ["Python", "SQL", "Statistics", "Machine Learning", "Pandas", "scikit-learn", "Data Visualization"],
        ["NumPy", "Jupyter", "Feature Engineering", "Deep Learning", "TensorFlow", "A/B Testing",
         "Communication", "Linear Algebra", "Git", "Matplotlib", "Seaborn", "R"],
    ),
    (
        "Data Engineer",
        ["Python", "SQL", "ETL", "Data Warehousing", "Apache Spark", "Apache Airflow", "Data Modeling"],
        ["PostgreSQL", "AWS", "Docker", "Apache Kafka", "dbt", "Big Data", "Linux", "Git", "Snowflake", "Bash",
         "BigQuery"],
    ),
    (
        "Machine Learning Engineer",
        ["Python", "Machine Learning", "Deep Learning", "PyTorch", "scikit-learn", "MLOps", "Docker"],
        ["SQL", "TensorFlow", "Feature Engineering", "NumPy", "Pandas", "AWS", "Git", "Linear Algebra",
         "Kubernetes", "MLflow", "Keras"],
    ),
    (
        "AI Engineer",
        ["Python", "Large Language Models", "Prompt Engineering", "Deep Learning", "PyTorch",
         "Natural Language Processing", "REST APIs"],
        ["Hugging Face", "LangChain", "FastAPI", "Docker", "Generative AI", "Computer Vision", "Git", "SQL",
         "Machine Learning", "Flask"],
    ),
    (
        "Business Analyst",
        ["Business Analysis", "Requirements Gathering", "SQL", "Excel", "Communication", "Data Visualization",
         "Stakeholder Management"],
        ["Agile", "Jira", "Power BI", "Presentation Skills", "Problem Solving", "Critical Thinking", "Tableau",
         "Microsoft Office"],
    ),
    (
        "Business Intelligence Developer",
        ["SQL", "Power BI", "Data Modeling", "Data Warehousing", "ETL", "Data Visualization", "Excel"],
        ["Tableau", "Python", "SQL Server", "DAX", "Looker Studio", "Communication", "Statistics",
         "Business Analysis"],
    ),
    (
        "Software Engineer",
        ["Data Structures and Algorithms", "Object-Oriented Programming", "Git", "Python", "Java", "SQL",
         "System Design", "REST APIs"],
        ["JavaScript", "Docker", "Linux", "Software Testing", "Agile", "Problem Solving", "Communication",
         "C++", "Teamwork", "C#", ".NET", "Spring Boot"],
    ),
    (
        "Frontend Developer",
        ["HTML", "CSS", "JavaScript", "React", "Responsive Design", "Git", "TypeScript"],
        ["REST APIs", "Tailwind CSS", "Next.js", "Web Accessibility", "Figma", "Jest", "Bootstrap", "Angular",
         "Vue.js", "Problem Solving"],
    ),
    (
        "Backend Developer",
        ["Python", "SQL", "REST APIs", "PostgreSQL", "Git", "Node.js", "Docker", "System Design"],
        ["Django", "FastAPI", "Express.js", "Redis", "MongoDB", "Linux", "Software Testing", "Microservices",
         "AWS", "Java", "Go", "Elasticsearch"],
    ),
    (
        "Full Stack Developer",
        ["HTML", "CSS", "JavaScript", "React", "Node.js", "SQL", "Git", "REST APIs"],
        ["TypeScript", "Express.js", "PostgreSQL", "MongoDB", "Docker", "Next.js", "Responsive Design",
         "Software Testing", "Problem Solving"],
    ),
    (
        "Mobile App Developer",
        ["Flutter", "Dart", "Kotlin", "REST APIs", "Git", "Android Studio", "Firebase"],
        ["React Native", "JavaScript", "Swift", "Xcode", "Java", "SQL", "Problem Solving", "Software Testing"],
    ),
    (
        "DevOps Engineer",
        ["Linux", "Docker", "Kubernetes", "CI/CD", "Git", "Bash", "AWS", "Terraform"],
        ["Jenkins", "GitHub Actions", "Ansible", "Monitoring", "Prometheus", "Grafana", "Python", "Nginx",
         "Infrastructure as Code", "Networking"],
    ),
    (
        "Cloud Engineer",
        ["AWS", "Cloud Computing", "Linux", "Networking", "Terraform", "Docker", "Infrastructure as Code"],
        ["Azure", "Google Cloud", "Kubernetes", "Python", "Bash", "CI/CD", "Monitoring", "Network Security",
         "Git"],
    ),
    (
        "QA Engineer",
        ["Software Testing", "Test Automation", "Selenium", "Postman", "Jira", "Attention to Detail"],
        ["SQL", "Python", "JavaScript", "Cypress", "Playwright", "pytest", "JUnit", "Git", "Agile",
         "Communication", "REST APIs"],
    ),
    (
        "Cybersecurity Analyst",
        ["Network Security", "Networking", "Linux", "Incident Response", "Penetration Testing", "Wireshark"],
        ["Cryptography", "Nmap", "Burp Suite", "Metasploit", "Splunk", "Kali Linux", "Python", "Bash",
         "Vulnerability Assessment", "Communication", "Active Directory"],
    ),
    (
        "Database Administrator",
        ["SQL", "PostgreSQL", "MySQL", "Database Design", "Backup and Recovery", "Performance Tuning", "Linux"],
        ["SQL Server", "Oracle Database", "Bash", "Python", "MongoDB", "Monitoring", "Data Modeling",
         "Troubleshooting", "Attention to Detail"],
    ),
    (
        "Network Engineer",
        ["Networking", "Routing and Switching", "Cisco IOS", "Network Security", "Troubleshooting", "Linux"],
        ["Wireshark", "Firewalls", "Python", "Bash", "Cloud Computing", "Monitoring", "Communication",
         "Windows Server", "Active Directory"],
    ),
    (
        "IT Support Specialist",
        ["Troubleshooting", "Customer Service", "Windows Server", "Active Directory", "Networking",
         "Hardware Support", "Communication", "Microsoft Office"],
        ["Linux", "PowerShell", "Jira", "Time Management", "Problem Solving", "Cloud Computing", "Excel"],
    ),
    (
        "Product Manager",
        ["Product Strategy", "Product Roadmapping", "Stakeholder Management", "Communication", "Agile",
         "User Research", "Jira"],
        ["SQL", "Excel", "Scrum", "A/B Testing", "Presentation Skills", "Leadership", "Critical Thinking",
         "Market Research", "Figma", "Negotiation"],
    ),
    (
        "Project Manager",
        ["Project Planning", "Risk Management", "Stakeholder Management", "Communication", "Agile", "Scrum",
         "Budgeting", "Leadership"],
        ["Jira", "Microsoft Project", "Excel", "Time Management", "Negotiation", "Presentation Skills", "Trello",
         "Problem Solving", "Confluence"],
    ),
    (
        "UI/UX Designer",
        ["Figma", "User Research", "Wireframing", "Prototyping", "Usability Testing", "Visual Design",
         "Communication"],
        ["Adobe XD", "Adobe Photoshop", "HTML", "CSS", "Web Accessibility", "Responsive Design", "Creativity",
         "Empathy", "Canva", "Design Systems"],
    ),
    (
        "Digital Marketing Specialist",
        ["SEO", "Google Ads", "Google Analytics", "Social Media Marketing", "Content Marketing", "Communication",
         "Email Marketing"],
        ["Copywriting", "Canva", "WordPress", "Mailchimp", "Google Search Console", "Excel", "Creativity",
         "Data Visualization", "Market Research"],
    ),
    (
        "Technical Writer",
        ["Technical Documentation", "Writing", "API Documentation", "Markdown", "Communication",
         "Attention to Detail", "Git"],
        ["REST APIs", "HTML", "Python", "Confluence", "Microsoft Office", "Agile", "Jira"],
    ),
    (
        "Financial Analyst",
        ["Excel", "Financial Modeling", "Financial Analysis", "Accounting", "Valuation", "Statistics",
         "Communication", "Presentation Skills"],
        ["SQL", "Power BI", "Python", "Forecasting", "Budgeting", "Attention to Detail", "Microsoft Office",
         "Critical Thinking"],
    ),
    (
        "Embedded Systems Engineer",
        ["C", "C++", "Microcontrollers", "RTOS", "Circuit Design", "Git", "Linux"],
        ["Python", "FreeRTOS", "Arduino", "Raspberry Pi", "PCB Design", "Signal Processing", "IoT", "KiCad",
         "MATLAB", "Troubleshooting", "Problem Solving"],
    ),
]

# --------------------------------------------------------------------------- aliases

# {"Canonical": ["alias", ...]}; every key must be a skill used by a role. Matching is case-insensitive.
ALIASES: dict[str, list[str]] = {
    "JavaScript": ["JS", "Java Script", "ECMAScript", "ES6"],
    "TypeScript": ["TS"],
    "Python": ["Python3", "Python 3", "Py"],
    "React": ["ReactJS", "React.js", "React JS"],
    "Node.js": ["Node", "NodeJS", "Node JS"],
    "Express.js": ["Express", "ExpressJS"],
    "Next.js": ["NextJS", "Next JS"],
    "Vue.js": ["Vue", "VueJS"],
    "Angular": ["AngularJS", "Angular JS"],
    "PostgreSQL": ["Postgres", "Postgre SQL"],
    "MySQL": ["My SQL"],
    "SQL Server": ["MS SQL Server", "MSSQL", "Microsoft SQL Server", "T-SQL"],
    "SQL": ["Structured Query Language", "SQL Queries"],
    "MongoDB": ["Mongo", "Mongo DB"],
    "Jupyter": ["Jupyter Notebook", "Jupyter Notebooks", "JupyterLab", "Jupyter Lab", "IPython Notebook"],
    "Excel": ["MS Excel", "Microsoft Excel", "Advanced Excel", "Excel Spreadsheets"],
    "Power BI": ["PowerBI", "MS Power BI", "Microsoft Power BI"],
    "Tableau": ["Tableau Desktop", "Tableau Public"],
    "Looker Studio": ["Google Data Studio", "Data Studio"],
    "scikit-learn": ["Sklearn", "Scikit Learn", "Sci-kit Learn"],
    "TensorFlow": ["TF", "Tensor Flow"],
    "PyTorch": ["Torch"],
    "Hugging Face": ["HuggingFace", "Hugging Face Transformers"],
    "AWS": ["AWS Cloud", "Amazon Web Services", "Amazon AWS"],
    "Azure": ["Microsoft Azure", "MS Azure", "Azure Cloud"],
    "Google Cloud": ["GCP", "Google Cloud Platform"],
    "Kubernetes": ["K8s"],
    "Go": ["Golang", "Go Lang"],
    "C#": ["C sharp", "CSharp", "C-Sharp"],
    "C++": ["CPP", "C plus plus"],
    ".NET": ["Dot Net", "DotNet", ".NET Core", "ASP.NET"],
    "HTML": ["HTML5"],
    "CSS": ["CSS3"],
    "Bash": ["Shell Scripting", "Bash Scripting", "Shell"],
    "Linux": ["Ubuntu", "GNU/Linux"],
    "PowerShell": ["Power Shell"],
    "Machine Learning": ["ML"],
    "Deep Learning": ["DL", "Neural Networks"],
    "Natural Language Processing": ["NLP"],
    "Large Language Models": ["LLM", "LLMs"],
    "Generative AI": ["GenAI", "Gen AI"],
    "Data Visualization": ["Data Visualisation", "Data Viz", "Dashboards"],
    "Statistics": ["Statistical Analysis", "Stats"],
    "Data Cleaning": ["Data Wrangling", "Data Cleansing"],
    "A/B Testing": ["AB Testing", "Split Testing"],
    "ETL": ["ETL Pipelines", "Extract Transform Load", "ELT"],
    "Data Warehousing": ["Data Warehouse"],
    "Data Modeling": ["Data Modelling"],
    "REST APIs": ["REST", "RESTful APIs", "REST API", "RESTful"],
    "CI/CD": ["CICD", "CI CD", "Continuous Integration", "Continuous Delivery"],
    "Infrastructure as Code": ["IaC"],
    "Object-Oriented Programming": ["OOP", "Object Oriented Programming"],
    "Data Structures and Algorithms": ["DSA", "Data Structures", "Algorithms", "Data Structures & Algorithms"],
    "Apache Spark": ["Spark", "PySpark"],
    "Apache Airflow": ["Airflow"],
    "Apache Kafka": ["Kafka"],
    "BigQuery": ["Google BigQuery"],
    "Elasticsearch": ["Elastic Search"],
    "Adobe Photoshop": ["Photoshop"],
    "Adobe XD": ["Adobe Experience Design"],
    "Google Analytics": ["GA4", "Google Analytics 4"],
    "SEO": ["Search Engine Optimization", "Search Engine Optimisation"],
    "Microsoft Office": ["MS Office", "Office 365", "Microsoft 365"],
    "Microsoft Project": ["MS Project"],
    "Active Directory": ["Microsoft Active Directory"],
    "Selenium": ["Selenium WebDriver"],
    "Software Testing": ["QA Testing", "Manual Testing", "Quality Assurance"],
    "Test Automation": ["Automation Testing", "Automated Testing"],
    "Penetration Testing": ["Pen Testing", "Pentesting", "Ethical Hacking"],
    "Networking": ["Computer Networking", "Computer Networks", "TCP/IP"],
    "Cloud Computing": ["Cloud"],
    "Monitoring": ["Observability"],
    "Communication": ["Communication Skills", "Verbal Communication", "Written Communication"],
    "Teamwork": ["Team Player", "Collaboration", "Team Work"],
    "Problem Solving": ["Problem-Solving"],
    "Presentation Skills": ["Presentations", "Public Speaking"],
    "Leadership": ["Team Leadership"],
    "Financial Modeling": ["Financial Modelling"],
    "Product Roadmapping": ["Roadmapping", "Product Roadmap"],
    "Technical Documentation": ["Technical Writing", "Documentation"],
    "Microcontrollers": ["MCU", "Microcontroller"],
    "RTOS": ["Real-Time Operating Systems", "Real Time Operating System"],
    "IoT": ["Internet of Things"],
    "Tailwind CSS": ["Tailwind", "TailwindCSS"],
    "FastAPI": ["Fast API"],
    "Spring Boot": ["Spring", "SpringBoot"],
    "Jira": ["Atlassian Jira"],
    "Agile": ["Agile Methodologies", "Agile Methodology"],
    "Firebase": ["Google Firebase"],
    "Customer Service": ["Customer Support"],
    "Web Accessibility": ["Accessibility", "a11y", "WCAG"],
    "Responsive Design": ["Responsive Web Design", "Mobile-First Design"],
    "Usability Testing": ["User Testing"],
    "User Research": ["UX Research"],
    "Wireframing": ["Wireframes"],
}

# --------------------------------------------------------------------------- resources

_FCC = "https://www.freecodecamp.org/learn/"
_KAGGLE = "https://www.kaggle.com/learn"
_OCW = "https://ocw.mit.edu/"
_SKILLSHOP = "https://skillshop.withgoogle.com/"
_MS_TRAINING = "https://learn.microsoft.com/en-us/training/"
_AWS_SB = "https://skillbuilder.aws/"
_KHAN_CAREERS = "https://www.khanacademy.org/college-careers-more"

# Skill -> list of (title, url, hours).
RESOURCES: dict[str, list[tuple[str, str, float]]] = {
    # languages
    "Python": [
        ("CS50's Introduction to Programming with Python", "https://cs50.harvard.edu/python/", 60),
        ("Kaggle Learn: Python", f"{_KAGGLE}/python", 5),
        ("The Python Tutorial (official docs)", "https://docs.python.org/3/tutorial/", 10),
    ],
    "SQL": [
        ("Kaggle Learn: Intro to SQL", f"{_KAGGLE}/intro-to-sql", 4),
        ("CS50's Introduction to Databases with SQL", "https://cs50.harvard.edu/sql/", 40),
        ("Khan Academy: Intro to SQL", "https://www.khanacademy.org/computing/computer-programming/sql", 6),
    ],
    "JavaScript": [
        ("freeCodeCamp: JavaScript Algorithms and Data Structures",
         f"{_FCC}javascript-algorithms-and-data-structures-v8/", 60),
        ("The Odin Project: JavaScript",
         "https://www.theodinproject.com/paths/full-stack-javascript/courses/javascript", 80),
    ],
    "TypeScript": [
        ("The TypeScript Handbook (official docs)", "https://www.typescriptlang.org/docs/handbook/intro.html", 8),
    ],
    "Java": [
        ("The Java Tutorials (official docs)", "https://docs.oracle.com/javase/tutorial/", 30),
        ("MIT OCW 6.092 Introduction to Programming in Java",
         "https://ocw.mit.edu/courses/6-092-introduction-to-programming-in-java-january-iap-2010/", 20),
    ],
    "C": [
        ("CS50x: Introduction to Computer Science (weeks 1-5 are in C)", "https://cs50.harvard.edu/x/", 60),
    ],
    "C++": [
        ("MIT OCW 6.096 Introduction to C++",
         "https://ocw.mit.edu/courses/6-096-introduction-to-c-january-iap-2011/", 20),
        ("Standard C++ Foundation: Get Started", "https://isocpp.org/get-started", 4),
    ],
    "C#": [
        ("freeCodeCamp: Foundational C# with Microsoft", f"{_FCC}foundational-c-sharp-with-microsoft/", 35),
        ("C# documentation (Microsoft Learn)", "https://learn.microsoft.com/en-us/dotnet/csharp/", 10),
    ],
    "Go": [
        ("A Tour of Go (official)", "https://go.dev/tour/", 6),
        ("Go documentation", "https://go.dev/doc/", 8),
    ],
    "Kotlin": [
        ("Kotlin documentation (official)", "https://kotlinlang.org/docs/home.html", 10),
        ("Android Basics with Compose (official course)",
         "https://developer.android.com/courses/android-basics-compose/course", 40),
    ],
    "Swift": [
        ("The Swift Programming Language (official book)", "https://docs.swift.org/swift-book/", 15),
        ("SwiftUI Tutorials (official)", "https://developer.apple.com/tutorials/swiftui", 10),
    ],
    "Dart": [("Dart language documentation (official)", "https://dart.dev/guides", 8)],
    "R": [
        ("CS50's Introduction to Programming with R", "https://cs50.harvard.edu/r/", 40),
        ("An Introduction to R (official manual)", "https://cran.r-project.org/doc/manuals/r-release/R-intro.html", 8),
    ],
    "Bash": [
        ("freeCodeCamp: Relational Database (Bash and Linux labs)", f"{_FCC}relational-database/", 30),
        ("GNU Bash Reference Manual", "https://www.gnu.org/software/bash/manual/", 8),
    ],
    "HTML": [
        ("freeCodeCamp: Responsive Web Design", f"{_FCC}responsive-web-design/", 50),
        ("The Odin Project: Foundations", "https://www.theodinproject.com/paths/foundations/courses/foundations", 40),
    ],
    "CSS": [
        ("freeCodeCamp: Responsive Web Design", f"{_FCC}responsive-web-design/", 50),
        ("The Odin Project: Intermediate HTML and CSS",
         "https://www.theodinproject.com/paths/full-stack-javascript/courses/intermediate-html-and-css", 25),
    ],
    "PowerShell": [("PowerShell documentation (Microsoft Learn)", "https://learn.microsoft.com/en-us/powershell/", 8)],
    "DAX": [("DAX reference (Microsoft Learn)", "https://learn.microsoft.com/en-us/dax/", 8)],
    # tools
    "Excel": [
        ("Excel video training (Microsoft Support)",
         "https://support.microsoft.com/en-us/office/excel-video-training-9bc05390-e94c-46af-a5b3-d7c22f6990bb", 8),
        ("Microsoft Learn training", _MS_TRAINING, 6),
    ],
    "Tableau": [
        ("Tableau free training videos (official)", "https://www.tableau.com/learn/training", 10),
        ("Tableau Desktop help (official docs)", "https://help.tableau.com/current/pro/desktop/en-us/default.htm", 6),
    ],
    "Power BI": [
        ("Power BI learning paths (Microsoft Learn)", "https://learn.microsoft.com/en-us/training/powerplatform/power-bi", 20),
    ],
    "Looker Studio": [("Looker Studio Help (official)", "https://support.google.com/looker-studio/", 4)],
    "Git": [
        ("Pro Git book (official)", "https://git-scm.com/book/en/v2", 12),
        ("Introduction to Git (Microsoft Learn)", "https://learn.microsoft.com/en-us/training/modules/intro-to-git/", 1),
    ],
    "Docker": [
        ("Docker: Get started (official docs)", "https://docs.docker.com/get-started/", 6),
        ("Introduction to Docker containers (Microsoft Learn)",
         "https://learn.microsoft.com/en-us/training/modules/intro-to-docker-containers/", 1),
    ],
    "Kubernetes": [
        ("Kubernetes Basics tutorial (official docs)", "https://kubernetes.io/docs/tutorials/kubernetes-basics/", 6),
        ("Introduction to Kubernetes (Microsoft Learn)",
         "https://learn.microsoft.com/en-us/training/modules/intro-to-kubernetes/", 1),
    ],
    "AWS": [
        ("AWS Cloud Practitioner Essentials (AWS Skill Builder, free)",
         "https://explore.skillbuilder.aws/learn/course/external/view/elearning/134/aws-cloud-practitioner-essentials", 6),
        ("AWS Skill Builder", _AWS_SB, 10),
    ],
    "Azure": [
        ("Azure Fundamentals: Describe cloud concepts (Microsoft Learn)",
         "https://learn.microsoft.com/en-us/training/paths/az-900-describe-cloud-concepts/", 2),
        ("Azure training (Microsoft Learn)", "https://learn.microsoft.com/en-us/training/azure/", 10),
    ],
    "Google Cloud": [("Google Cloud documentation", "https://cloud.google.com/docs", 8)],
    "Jupyter": [
        ("Project Jupyter documentation (official)", "https://docs.jupyter.org/en/latest/", 3),
        ("freeCodeCamp: Data Analysis with Python", f"{_FCC}data-analysis-with-python/", 30),
    ],
    "Jira": [("Jira Software guides (official)", "https://www.atlassian.com/software/jira/guides", 3)],
    "Confluence": [("Confluence Cloud documentation (official)", "https://support.atlassian.com/confluence-cloud/", 3)],
    "Trello": [("Trello guide (official)", "https://trello.com/guide", 2)],
    "Linux": [
        ("The Linux command line for beginners (Ubuntu docs)",
         "https://ubuntu.com/tutorials/command-line-for-beginners", 3),
        ("freeCodeCamp: Relational Database (Bash and Linux labs)", f"{_FCC}relational-database/", 30),
    ],
    "Terraform": [("Terraform tutorials (official)", "https://developer.hashicorp.com/terraform/tutorials", 10)],
    "Ansible": [
        ("Getting started with Ansible (official docs)",
         "https://docs.ansible.com/ansible/latest/getting_started/index.html", 4),
    ],
    "Jenkins": [("Jenkins tutorials (official docs)", "https://www.jenkins.io/doc/tutorials/", 6)],
    "GitHub Actions": [("GitHub Actions documentation", "https://docs.github.com/en/actions", 6)],
    "Postman": [("Postman Learning Center (official docs)", "https://learning.postman.com/docs/", 5)],
    "Selenium": [("Selenium documentation (official)", "https://www.selenium.dev/documentation/", 8)],
    "Figma": [("Figma Help Center (official)", "https://help.figma.com/", 6)],
    "Adobe XD": [("Adobe XD help and tutorials (official)", "https://helpx.adobe.com/xd/", 4)],
    "Adobe Photoshop": [("Photoshop tutorials (official)", "https://helpx.adobe.com/photoshop/tutorials.html", 8)],
    "Canva": [("Canva Design School (official)", "https://www.canva.com/designschool/", 4)],
    "Google Analytics": [
        ("Google Skillshop", _SKILLSHOP, 6),
        ("Google Analytics Help (official)", "https://support.google.com/analytics/", 4),
    ],
    "Google Ads": [
        ("Google Skillshop", _SKILLSHOP, 8),
        ("Google Ads Help (official)", "https://support.google.com/google-ads/", 4),
    ],
    "Google Search Console": [("Search Console Help (official)", "https://support.google.com/webmasters/", 3)],
    "WordPress": [("Learn WordPress (official)", "https://learn.wordpress.org/", 8)],
    "Mailchimp": [("Mailchimp Help Center (official)", "https://mailchimp.com/help/", 3)],
    "Wireshark": [("Wireshark documentation (official)", "https://www.wireshark.org/docs/", 6)],
    "Nmap": [("Nmap Reference Guide (official)", "https://nmap.org/book/", 6)],
    "Burp Suite": [("PortSwigger Web Security Academy (official, free)", "https://portswigger.net/web-security", 40)],
    "Metasploit": [("Metasploit documentation (official)", "https://docs.metasploit.com/", 6)],
    "Splunk": [("Splunk documentation (official)", "https://docs.splunk.com/Documentation", 6)],
    "Kali Linux": [("Kali Linux documentation (official)", "https://www.kali.org/docs/", 5)],
    "MATLAB": [
        ("MATLAB Onramp (official, free)", "https://matlabacademy.mathworks.com/details/matlab-onramp/gettingstarted", 2),
        ("MATLAB documentation", "https://www.mathworks.com/help/matlab/", 6),
    ],
    "Android Studio": [
        ("Android Basics with Compose (official course)",
         "https://developer.android.com/courses/android-basics-compose/course", 40),
    ],
    "Xcode": [("Xcode documentation (official)", "https://developer.apple.com/documentation/xcode", 4)],
    "Apache Airflow": [
        ("Apache Airflow documentation (official)", "https://airflow.apache.org/docs/apache-airflow/stable/", 8),
    ],
    "Apache Spark": [("Apache Spark documentation (official)", "https://spark.apache.org/docs/latest/", 10)],
    "Apache Kafka": [("Apache Kafka documentation (official)", "https://kafka.apache.org/documentation/", 8)],
    "Redis": [("Redis documentation (official)", "https://redis.io/docs/latest/", 4)],
    "MongoDB": [
        ("MongoDB Manual (official)", "https://www.mongodb.com/docs/manual/", 8),
        ("freeCodeCamp: Back End Development and APIs", f"{_FCC}back-end-development-and-apis/", 30),
    ],
    "PostgreSQL": [
        ("PostgreSQL tutorial (official docs)", "https://www.postgresql.org/docs/current/tutorial.html", 6),
        ("freeCodeCamp: Relational Database", f"{_FCC}relational-database/", 30),
    ],
    "MySQL": [("Getting Started with MySQL (official docs)", "https://dev.mysql.com/doc/mysql-getting-started/en/", 4)],
    "SQL Server": [
        ("Get started querying with Transact-SQL (Microsoft Learn)",
         "https://learn.microsoft.com/en-us/training/paths/get-started-querying-with-transact-sql/", 6),
        ("SQL Server documentation (Microsoft Learn)", "https://learn.microsoft.com/en-us/sql/sql-server/", 8),
    ],
    "Oracle Database": [("Oracle Database documentation (official)", "https://docs.oracle.com/en/database/", 8)],
    "Firebase": [("Firebase documentation (official)", "https://firebase.google.com/docs", 6)],
    "Nginx": [("nginx documentation (official)", "https://nginx.org/en/docs/", 4)],
    "Prometheus": [("Prometheus overview (official docs)", "https://prometheus.io/docs/introduction/overview/", 4)],
    "Grafana": [("Grafana documentation (official)", "https://grafana.com/docs/grafana/latest/", 5)],
    "Active Directory": [
        ("Active Directory Domain Services overview (Microsoft Learn)",
         "https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/get-started/virtual-dc/active-directory-domain-services-overview", 4),
    ],
    "Windows Server": [("Windows Server documentation (Microsoft Learn)", "https://learn.microsoft.com/en-us/windows-server/", 8)],
    "Microsoft Office": [("Microsoft 365 training (Microsoft Support)", "https://support.microsoft.com/en-us/training", 6)],
    "Microsoft Project": [("Microsoft Project help and learning (official)", "https://support.microsoft.com/en-us/project", 4)],
    "Hugging Face": [("Hugging Face Learn (official courses)", "https://huggingface.co/learn", 20)],
    "MLflow": [("MLflow documentation (official)", "https://mlflow.org/docs/latest/index.html", 4)],
    "Arduino": [("Arduino documentation (official)", "https://docs.arduino.cc/", 6)],
    "Raspberry Pi": [("Raspberry Pi documentation (official)", "https://www.raspberrypi.com/documentation/", 5)],
    "KiCad": [("KiCad documentation (official)", "https://docs.kicad.org/", 8)],
    "dbt": [("dbt documentation (official)", "https://docs.getdbt.com/", 6)],
    "Snowflake": [("Snowflake documentation (official)", "https://docs.snowflake.com/", 6)],
    "BigQuery": [("BigQuery documentation (official)", "https://cloud.google.com/bigquery/docs", 6)],
    "Elasticsearch": [
        ("Elasticsearch Guide (official docs)",
         "https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html", 8),
    ],
    "Cisco IOS": [
        ("Networking basics (Cisco)",
         "https://www.cisco.com/c/en/us/solutions/small-business/resource-center/networking/networking-basics.html", 3),
    ],
    "Markdown": [
        ("Basic writing and formatting syntax (GitHub Docs)",
         "https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax", 1),
    ],
    # frameworks
    "React": [
        ("The Odin Project: React", "https://www.theodinproject.com/paths/full-stack-javascript/courses/react", 40),
        ("freeCodeCamp: Front End Development Libraries", f"{_FCC}front-end-development-libraries/", 40),
    ],
    "Angular": [("Angular documentation (official)", "https://angular.dev/overview", 12)],
    "Vue.js": [("Vue.js guide (official docs)", "https://vuejs.org/guide/introduction.html", 10)],
    "Node.js": [
        ("The Odin Project: NodeJS", "https://www.theodinproject.com/paths/full-stack-javascript/courses/nodejs", 50),
        ("freeCodeCamp: Back End Development and APIs", f"{_FCC}back-end-development-and-apis/", 30),
    ],
    "Express.js": [
        ("Express getting started (official docs)", "https://expressjs.com/en/starter/installing.html", 4),
        ("freeCodeCamp: Back End Development and APIs", f"{_FCC}back-end-development-and-apis/", 30),
    ],
    "Next.js": [("Learn Next.js (official)", "https://nextjs.org/learn", 10)],
    "Django": [
        ("Django tutorial (official docs)", "https://docs.djangoproject.com/en/stable/intro/tutorial01/", 8),
        ("CS50's Web Programming with Python and JavaScript", "https://cs50.harvard.edu/web/", 60),
    ],
    "Flask": [("Flask tutorial (official docs)", "https://flask.palletsprojects.com/en/stable/tutorial/", 6)],
    "FastAPI": [("FastAPI tutorial (official docs)", "https://fastapi.tiangolo.com/tutorial/", 8)],
    "Spring Boot": [("Spring Boot guides (official)", "https://spring.io/guides", 10)],
    ".NET": [("Learn .NET (official)", "https://dotnet.microsoft.com/en-us/learn", 10)],
    "Flutter": [("Flutter documentation (official)", "https://docs.flutter.dev/", 15)],
    "React Native": [("React Native documentation (official)", "https://reactnative.dev/docs/getting-started", 10)],
    "Tailwind CSS": [("Tailwind CSS documentation (official)", "https://tailwindcss.com/docs", 4)],
    "Bootstrap": [
        ("Bootstrap documentation (official)", "https://getbootstrap.com/docs/", 4),
        ("freeCodeCamp: Front End Development Libraries", f"{_FCC}front-end-development-libraries/", 40),
    ],
    "Pandas": [
        ("Kaggle Learn: Pandas", f"{_KAGGLE}/pandas", 4),
        ("10 minutes to pandas (official docs)", "https://pandas.pydata.org/docs/user_guide/10min.html", 2),
    ],
    "NumPy": [
        ("NumPy: the absolute basics for beginners (official docs)",
         "https://numpy.org/doc/stable/user/absolute_beginners.html", 3),
        ("freeCodeCamp: Data Analysis with Python", f"{_FCC}data-analysis-with-python/", 30),
    ],
    "Matplotlib": [
        ("Matplotlib tutorials (official docs)", "https://matplotlib.org/stable/tutorials/index.html", 4),
        ("Kaggle Learn: Data Visualization", f"{_KAGGLE}/data-visualization", 4),
    ],
    "Seaborn": [("Seaborn tutorial (official docs)", "https://seaborn.pydata.org/tutorial.html", 3)],
    "scikit-learn": [
        ("scikit-learn: Getting Started (official docs)", "https://scikit-learn.org/stable/getting_started.html", 3),
        ("Kaggle Learn: Intro to Machine Learning", f"{_KAGGLE}/intro-to-machine-learning", 3),
    ],
    "TensorFlow": [
        ("TensorFlow tutorials (official)", "https://www.tensorflow.org/tutorials", 10),
        ("freeCodeCamp: Machine Learning with Python", f"{_FCC}machine-learning-with-python/", 30),
    ],
    "PyTorch": [("PyTorch tutorials (official)", "https://pytorch.org/tutorials/", 10)],
    "Keras": [("Keras: Getting started (official docs)", "https://keras.io/getting_started/", 3)],
    "OpenCV": [("OpenCV-Python tutorials (official docs)", "https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html", 10)],
    "LangChain": [("LangChain documentation (official)", "https://python.langchain.com/docs/introduction/", 6)],
    "Jest": [("Jest: Getting Started (official docs)", "https://jestjs.io/docs/getting-started", 3)],
    "pytest": [("pytest documentation (official)", "https://docs.pytest.org/en/stable/", 4)],
    "JUnit": [("JUnit 5 User Guide (official)", "https://junit.org/junit5/docs/current/user-guide/", 4)],
    "Cypress": [("Cypress documentation (official)", "https://docs.cypress.io/", 6)],
    "Playwright": [("Playwright: Getting started (official docs)", "https://playwright.dev/docs/intro", 4)],
    "FreeRTOS": [("FreeRTOS documentation (official)", "https://www.freertos.org/", 8)],
    # soft skills
    "Communication": [
        ("MIT OCW 15.279 Management Communication for Undergraduates",
         "https://ocw.mit.edu/courses/15-279-management-communication-for-undergraduates-fall-2012/", 20),
        ("Khan Academy: College, careers, and more", _KHAN_CAREERS, 4),
    ],
    "Problem Solving": [
        ("MIT OCW 6.0001 Introduction to Computer Science and Programming in Python",
         "https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/", 40),
        ("Khan Academy: Algorithms", "https://www.khanacademy.org/computing/computer-science/algorithms", 10),
    ],
    "Teamwork": [
        ("Khan Academy: College, careers, and more", _KHAN_CAREERS, 3),
        ("The Odin Project: Getting Hired",
         "https://www.theodinproject.com/paths/full-stack-javascript/courses/getting-hired", 6),
    ],
    "Critical Thinking": [
        ("Khan Academy: Statistics and probability", "https://www.khanacademy.org/math/statistics-probability", 20),
        ("MIT OpenCourseWare", _OCW, 10),
    ],
    "Time Management": [("Khan Academy: College, careers, and more", _KHAN_CAREERS, 3)],
    "Presentation Skills": [
        ("MIT OCW 15.279 Management Communication for Undergraduates",
         "https://ocw.mit.edu/courses/15-279-management-communication-for-undergraduates-fall-2012/", 20),
    ],
    "Leadership": [
        ("MIT OpenCourseWare (Sloan School of Management courses)", _OCW, 15),
        ("Khan Academy: College, careers, and more", _KHAN_CAREERS, 3),
    ],
    "Attention to Detail": [
        ("Kaggle Learn: Data Cleaning", f"{_KAGGLE}/data-cleaning", 4),
        ("freeCodeCamp: Quality Assurance", f"{_FCC}quality-assurance/", 30),
    ],
    "Adaptability": [("Khan Academy: College, careers, and more", _KHAN_CAREERS, 3)],
    "Negotiation": [
        ("MIT OpenCourseWare (negotiation and management communication courses)", _OCW, 15),
        ("Khan Academy: College, careers, and more", _KHAN_CAREERS, 3),
    ],
    "Creativity": [
        ("Canva Design School (official)", "https://www.canva.com/designschool/", 4),
        ("Khan Academy: Computer programming", "https://www.khanacademy.org/computing/computer-programming", 10),
    ],
    "Empathy": [
        ("Khan Academy: College, careers, and more", _KHAN_CAREERS, 3),
        ("Figma Help Center: design basics (official)", "https://help.figma.com/", 4),
    ],
    "Writing": [
        ("Khan Academy: Grammar", "https://www.khanacademy.org/humanities/grammar", 10),
        ("Microsoft Writing Style Guide", "https://learn.microsoft.com/en-us/style-guide/welcome/", 4),
    ],
    # domains
    "Statistics": [
        ("Khan Academy: Statistics and probability", "https://www.khanacademy.org/math/statistics-probability", 30),
        ("MIT OCW 18.05 Introduction to Probability and Statistics",
         "https://ocw.mit.edu/courses/18-05-introduction-to-probability-and-statistics-spring-2014/", 40),
    ],
    "Data Visualization": [
        ("Kaggle Learn: Data Visualization", f"{_KAGGLE}/data-visualization", 4),
        ("freeCodeCamp: Data Visualization", f"{_FCC}data-visualization/", 30),
    ],
    "Data Cleaning": [
        ("Kaggle Learn: Data Cleaning", f"{_KAGGLE}/data-cleaning", 4),
        ("Kaggle Learn: Pandas", f"{_KAGGLE}/pandas", 4),
    ],
    "A/B Testing": [
        ("Khan Academy: Statistics and probability", "https://www.khanacademy.org/math/statistics-probability", 30),
        ("MIT OCW 15.071 The Analytics Edge", "https://ocw.mit.edu/courses/15-071-the-analytics-edge-spring-2017/", 40),
    ],
    "Machine Learning": [
        ("Kaggle Learn: Intro to Machine Learning", f"{_KAGGLE}/intro-to-machine-learning", 3),
        ("Kaggle Learn: Intermediate Machine Learning", f"{_KAGGLE}/intermediate-machine-learning", 4),
        ("MIT OCW 6.036 Introduction to Machine Learning",
         "https://ocw.mit.edu/courses/6-036-introduction-to-machine-learning-fall-2020/", 60),
    ],
    "Deep Learning": [
        ("Kaggle Learn: Intro to Deep Learning", f"{_KAGGLE}/intro-to-deep-learning", 4),
        ("freeCodeCamp: Machine Learning with Python", f"{_FCC}machine-learning-with-python/", 30),
    ],
    "Natural Language Processing": [
        ("Hugging Face Learn: NLP course (official)", "https://huggingface.co/learn/nlp-course/chapter1/1", 20),
        ("CS50's Introduction to Artificial Intelligence with Python", "https://cs50.harvard.edu/ai/", 60),
    ],
    "Computer Vision": [
        ("Kaggle Learn: Computer Vision", f"{_KAGGLE}/computer-vision", 4),
        ("OpenCV-Python tutorials (official docs)", "https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html", 10),
    ],
    "Data Modeling": [
        ("Design a data model in Power BI (Microsoft Learn)",
         "https://learn.microsoft.com/en-us/training/modules/design-a-data-model-in-power-bi/", 2),
        ("PostgreSQL tutorial (official docs)", "https://www.postgresql.org/docs/current/tutorial.html", 6),
    ],
    "ETL": [
        ("Extract, transform, and load (Microsoft Learn architecture guide)",
         "https://learn.microsoft.com/en-us/azure/architecture/data-guide/relational-data/etl", 1),
        ("Apache Airflow documentation (official)", "https://airflow.apache.org/docs/apache-airflow/stable/", 8),
    ],
    "Data Warehousing": [
        ("Data warehousing (Microsoft Learn architecture guide)",
         "https://learn.microsoft.com/en-us/azure/architecture/data-guide/relational-data/data-warehousing", 1),
        ("Kaggle Learn: Advanced SQL", f"{_KAGGLE}/advanced-sql", 4),
    ],
    "Big Data": [
        ("Apache Spark documentation (official)", "https://spark.apache.org/docs/latest/", 10),
        ("Apache Hadoop documentation (official)", "https://hadoop.apache.org/docs/stable/", 8),
    ],
    "Feature Engineering": [("Kaggle Learn: Feature Engineering", f"{_KAGGLE}/feature-engineering", 5)],
    "MLOps": [
        ("MLflow documentation (official)", "https://mlflow.org/docs/latest/index.html", 4),
        ("Docker: Get started (official docs)", "https://docs.docker.com/get-started/", 6),
    ],
    "Large Language Models": [
        ("Hugging Face Learn (official courses)", "https://huggingface.co/learn", 20),
        ("CS50's Introduction to Artificial Intelligence with Python", "https://cs50.harvard.edu/ai/", 60),
    ],
    "Prompt Engineering": [
        ("Hugging Face Learn (official courses)", "https://huggingface.co/learn", 20),
        ("LangChain documentation (official)", "https://python.langchain.com/docs/introduction/", 6),
    ],
    "Generative AI": [
        ("Hugging Face Learn (official courses)", "https://huggingface.co/learn", 20),
        ("Microsoft Learn training", _MS_TRAINING, 8),
    ],
    "Linear Algebra": [
        ("Khan Academy: Linear algebra", "https://www.khanacademy.org/math/linear-algebra", 30),
        ("MIT OCW 18.06 Linear Algebra", "https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/", 60),
    ],
    "Business Analysis": [
        ("MIT OCW 15.071 The Analytics Edge", "https://ocw.mit.edu/courses/15-071-the-analytics-edge-spring-2017/", 40),
        ("Get started with data analytics (Microsoft Learn)",
         "https://learn.microsoft.com/en-us/training/modules/data-analytics-microsoft/", 1),
    ],
    "Requirements Gathering": [
        ("What is Agile? (Microsoft Learn)", "https://learn.microsoft.com/en-us/devops/plan/what-is-agile", 1),
        ("Jira Software guides (official)", "https://www.atlassian.com/software/jira/guides", 3),
    ],
    "Agile": [
        ("What is Agile? (Microsoft Learn)", "https://learn.microsoft.com/en-us/devops/plan/what-is-agile", 1),
        ("Agile guides (Atlassian)", "https://www.atlassian.com/agile", 4),
    ],
    "Scrum": [
        ("What is Scrum? (Microsoft Learn)", "https://learn.microsoft.com/en-us/devops/plan/what-is-scrum", 1),
        ("The Scrum Guide (official)", "https://scrumguides.org/", 2),
    ],
    "Software Testing": [
        ("freeCodeCamp: Quality Assurance", f"{_FCC}quality-assurance/", 30),
        ("pytest documentation (official)", "https://docs.pytest.org/en/stable/", 4),
    ],
    "Test Automation": [
        ("Selenium documentation (official)", "https://www.selenium.dev/documentation/", 8),
        ("Playwright: Getting started (official docs)", "https://playwright.dev/docs/intro", 4),
    ],
    "REST APIs": [
        ("freeCodeCamp: Back End Development and APIs", f"{_FCC}back-end-development-and-apis/", 30),
        ("Postman Learning Center (official docs)", "https://learning.postman.com/docs/", 5),
    ],
    "System Design": [
        ("MIT OCW 6.033 Computer System Engineering",
         "https://ocw.mit.edu/courses/6-033-computer-system-engineering-spring-2018/", 60),
        ("AWS Architecture Center (official docs)", "https://aws.amazon.com/architecture/", 8),
    ],
    "Data Structures and Algorithms": [
        ("MIT OCW 6.006 Introduction to Algorithms",
         "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/", 60),
        ("Khan Academy: Algorithms", "https://www.khanacademy.org/computing/computer-science/algorithms", 10),
        ("freeCodeCamp: JavaScript Algorithms and Data Structures",
         f"{_FCC}javascript-algorithms-and-data-structures-v8/", 60),
    ],
    "Object-Oriented Programming": [
        ("MIT OCW 6.0001 Introduction to Computer Science and Programming in Python",
         "https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/", 40),
        ("The Java Tutorials (official docs)", "https://docs.oracle.com/javase/tutorial/", 30),
    ],
    "Microservices": [
        ("Microservices architecture (Microsoft Learn architecture guide)",
         "https://learn.microsoft.com/en-us/azure/architecture/guide/architecture-styles/microservices", 2),
        ("Docker: Get started (official docs)", "https://docs.docker.com/get-started/", 6),
    ],
    "Networking": [
        ("Khan Academy: Computers and the Internet", "https://www.khanacademy.org/computing/computers-and-internet", 8),
        ("Network fundamentals (Microsoft Learn)",
         "https://learn.microsoft.com/en-us/training/modules/network-fundamentals/", 1),
    ],
    "Routing and Switching": [
        ("Networking basics (Cisco)",
         "https://www.cisco.com/c/en/us/solutions/small-business/resource-center/networking/networking-basics.html", 3),
        ("Khan Academy: Computers and the Internet", "https://www.khanacademy.org/computing/computers-and-internet", 8),
    ],
    "Firewalls": [
        ("Network fundamentals (Microsoft Learn)",
         "https://learn.microsoft.com/en-us/training/modules/network-fundamentals/", 1),
        ("AWS Skill Builder", _AWS_SB, 6),
    ],
    "Network Security": [
        ("MIT OCW 6.858 Computer Systems Security",
         "https://ocw.mit.edu/courses/6-858-computer-systems-security-fall-2014/", 60),
        ("CS50's Introduction to Cybersecurity", "https://cs50.harvard.edu/cybersecurity/", 20),
    ],
    "Penetration Testing": [
        ("PortSwigger Web Security Academy (official, free)", "https://portswigger.net/web-security", 40),
        ("freeCodeCamp: Information Security", f"{_FCC}information-security/", 30),
    ],
    "Vulnerability Assessment": [
        ("Nmap Reference Guide (official)", "https://nmap.org/book/", 6),
        ("PortSwigger Web Security Academy (official, free)", "https://portswigger.net/web-security", 40),
    ],
    "Incident Response": [
        ("CS50's Introduction to Cybersecurity", "https://cs50.harvard.edu/cybersecurity/", 20),
        ("Splunk documentation (official)", "https://docs.splunk.com/Documentation", 6),
    ],
    "Cryptography": [
        ("Khan Academy: Cryptography", "https://www.khanacademy.org/computing/computer-science/cryptography", 6),
        ("MIT OCW 6.858 Computer Systems Security",
         "https://ocw.mit.edu/courses/6-858-computer-systems-security-fall-2014/", 60),
    ],
    "Cloud Computing": [
        ("AWS Cloud Practitioner Essentials (AWS Skill Builder, free)",
         "https://explore.skillbuilder.aws/learn/course/external/view/elearning/134/aws-cloud-practitioner-essentials", 6),
        ("Azure Fundamentals: Describe cloud concepts (Microsoft Learn)",
         "https://learn.microsoft.com/en-us/training/paths/az-900-describe-cloud-concepts/", 2),
    ],
    "CI/CD": [
        ("What is continuous integration? (Microsoft Learn)",
         "https://learn.microsoft.com/en-us/devops/develop/what-is-continuous-integration", 1),
        ("GitHub Actions documentation", "https://docs.github.com/en/actions", 6),
    ],
    "Infrastructure as Code": [
        ("What is infrastructure as code? (Microsoft Learn)",
         "https://learn.microsoft.com/en-us/devops/deliver/what-is-infrastructure-as-code", 1),
        ("Terraform tutorials (official)", "https://developer.hashicorp.com/terraform/tutorials", 10),
    ],
    "Monitoring": [
        ("Prometheus overview (official docs)", "https://prometheus.io/docs/introduction/overview/", 4),
        ("Grafana documentation (official)", "https://grafana.com/docs/grafana/latest/", 5),
    ],
    "Responsive Design": [
        ("freeCodeCamp: Responsive Web Design", f"{_FCC}responsive-web-design/", 50),
        ("The Odin Project: Advanced HTML and CSS",
         "https://www.theodinproject.com/paths/full-stack-javascript/courses/advanced-html-and-css", 25),
    ],
    "Web Accessibility": [
        ("freeCodeCamp: Responsive Web Design (accessibility module)", f"{_FCC}responsive-web-design/", 50),
        ("Accessibility fundamentals (Microsoft Learn)",
         "https://learn.microsoft.com/en-us/training/paths/accessibility-fundamentals/", 3),
    ],
    "User Research": [
        ("MIT OCW 6.831 User Interface Design and Implementation",
         "https://ocw.mit.edu/courses/6-831-user-interface-design-and-implementation-spring-2011/", 40),
        ("Figma Help Center (official)", "https://help.figma.com/", 6),
    ],
    "Wireframing": [("Figma Help Center (official)", "https://help.figma.com/", 6)],
    "Prototyping": [("Figma Help Center (official)", "https://help.figma.com/", 6)],
    "Usability Testing": [
        ("MIT OCW 6.831 User Interface Design and Implementation",
         "https://ocw.mit.edu/courses/6-831-user-interface-design-and-implementation-spring-2011/", 40),
    ],
    "Visual Design": [
        ("Canva Design School (official)", "https://www.canva.com/designschool/", 4),
        ("Figma Help Center (official)", "https://help.figma.com/", 6),
    ],
    "Design Systems": [("Figma Help Center (official)", "https://help.figma.com/", 6)],
    "SEO": [
        ("SEO Starter Guide (Google Search Central, official)",
         "https://developers.google.com/search/docs/fundamentals/seo-starter-guide", 3),
        ("Google Skillshop", _SKILLSHOP, 6),
    ],
    "Content Marketing": [
        ("Google Skillshop", _SKILLSHOP, 6),
        ("Learn WordPress (official)", "https://learn.wordpress.org/", 8),
    ],
    "Social Media Marketing": [
        ("Google Skillshop", _SKILLSHOP, 6),
        ("Canva Design School (official)", "https://www.canva.com/designschool/", 4),
    ],
    "Email Marketing": [("Mailchimp Help Center (official)", "https://mailchimp.com/help/", 3)],
    "Copywriting": [
        ("Khan Academy: Grammar", "https://www.khanacademy.org/humanities/grammar", 10),
        ("Google Skillshop", _SKILLSHOP, 6),
    ],
    "Market Research": [
        ("Google Skillshop", _SKILLSHOP, 6),
        ("Khan Academy: Statistics and probability", "https://www.khanacademy.org/math/statistics-probability", 30),
    ],
    "Technical Documentation": [
        ("Microsoft Writing Style Guide", "https://learn.microsoft.com/en-us/style-guide/welcome/", 4),
        ("Google developer documentation style guide (official)", "https://developers.google.com/style", 4),
    ],
    "API Documentation": [
        ("Google developer documentation style guide (official)", "https://developers.google.com/style", 4),
        ("Postman Learning Center (official docs)", "https://learning.postman.com/docs/", 5),
    ],
    "Financial Modeling": [
        ("Khan Academy: Finance and capital markets",
         "https://www.khanacademy.org/economics-finance-domain/core-finance", 20),
        ("MIT OCW 15.401 Finance Theory I", "https://ocw.mit.edu/courses/15-401-finance-theory-i-fall-2008/", 50),
    ],
    "Accounting": [
        ("Khan Academy: Finance and capital markets (accounting unit)",
         "https://www.khanacademy.org/economics-finance-domain/core-finance", 8),
        ("MIT OCW 15.501 Introduction to Financial and Managerial Accounting",
         "https://ocw.mit.edu/courses/15-501-introduction-to-financial-and-managerial-accounting-spring-2004/", 40),
    ],
    "Financial Analysis": [
        ("Khan Academy: Finance and capital markets",
         "https://www.khanacademy.org/economics-finance-domain/core-finance", 20),
        ("Excel video training (Microsoft Support)",
         "https://support.microsoft.com/en-us/office/excel-video-training-9bc05390-e94c-46af-a5b3-d7c22f6990bb", 8),
    ],
    "Valuation": [
        ("MIT OCW 15.401 Finance Theory I", "https://ocw.mit.edu/courses/15-401-finance-theory-i-fall-2008/", 50),
        ("Khan Academy: Finance and capital markets",
         "https://www.khanacademy.org/economics-finance-domain/core-finance", 20),
    ],
    "Forecasting": [
        ("Kaggle Learn: Time Series", f"{_KAGGLE}/time-series", 5),
        ("Khan Academy: Statistics and probability", "https://www.khanacademy.org/math/statistics-probability", 30),
    ],
    "Budgeting": [
        ("Khan Academy: Personal finance", "https://www.khanacademy.org/college-careers-more/personal-finance", 6),
        ("Excel video training (Microsoft Support)",
         "https://support.microsoft.com/en-us/office/excel-video-training-9bc05390-e94c-46af-a5b3-d7c22f6990bb", 8),
    ],
    "Microcontrollers": [
        ("Arduino documentation (official)", "https://docs.arduino.cc/", 6),
        ("MIT OCW 6.01SC Introduction to Electrical Engineering and Computer Science I",
         "https://ocw.mit.edu/courses/6-01sc-introduction-to-electrical-engineering-and-computer-science-i-spring-2011/", 50),
    ],
    "RTOS": [("FreeRTOS documentation (official)", "https://www.freertos.org/", 8)],
    "PCB Design": [("KiCad documentation (official)", "https://docs.kicad.org/", 8)],
    "Signal Processing": [
        ("MIT OCW 6.003 Signals and Systems", "https://ocw.mit.edu/courses/6-003-signals-and-systems-fall-2011/", 60),
        ("MATLAB Onramp (official, free)", "https://matlabacademy.mathworks.com/details/matlab-onramp/gettingstarted", 2),
    ],
    "IoT": [
        ("AWS IoT documentation (official)", "https://docs.aws.amazon.com/iot/", 6),
        ("Raspberry Pi documentation (official)", "https://www.raspberrypi.com/documentation/", 5),
    ],
    "Circuit Design": [
        ("Khan Academy: Electrical engineering", "https://www.khanacademy.org/science/electrical-engineering", 20),
        ("MIT OCW 6.002 Circuits and Electronics",
         "https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/", 60),
    ],
    "Product Strategy": [
        ("CS50 for MBAs", "https://cs50.harvard.edu/business/", 20),
        ("MIT OpenCourseWare: Sloan School of Management", "https://ocw.mit.edu/search/?d=Sloan%20School%20of%20Management", 15),
    ],
    "Product Roadmapping": [
        ("Jira Software guides (official)", "https://www.atlassian.com/software/jira/guides", 3),
        ("Agile guides (Atlassian)", "https://www.atlassian.com/agile", 4),
    ],
    "Stakeholder Management": [
        ("MIT OCW 15.279 Management Communication for Undergraduates",
         "https://ocw.mit.edu/courses/15-279-management-communication-for-undergraduates-fall-2012/", 20),
        ("Jira Software guides (official)", "https://www.atlassian.com/software/jira/guides", 3),
    ],
    "Project Planning": [
        ("MIT OCW 1.040 Project Management", "https://ocw.mit.edu/courses/1-040-project-management-spring-2009/", 40),
        ("Microsoft Project help and learning (official)", "https://support.microsoft.com/en-us/project", 4),
    ],
    "Risk Management": [
        ("MIT OCW 1.040 Project Management", "https://ocw.mit.edu/courses/1-040-project-management-spring-2009/", 40),
    ],
    "Database Design": [
        ("CS50's Introduction to Databases with SQL", "https://cs50.harvard.edu/sql/", 40),
        ("PostgreSQL tutorial (official docs)", "https://www.postgresql.org/docs/current/tutorial.html", 6),
    ],
    "Backup and Recovery": [
        ("PostgreSQL: Backup and Restore (official docs)", "https://www.postgresql.org/docs/current/backup.html", 3),
        ("SQL Server documentation (Microsoft Learn)", "https://learn.microsoft.com/en-us/sql/sql-server/", 8),
    ],
    "Performance Tuning": [
        ("PostgreSQL: Performance Tips (official docs)", "https://www.postgresql.org/docs/current/performance-tips.html", 3),
        ("MySQL: Optimization (official docs)", "https://dev.mysql.com/doc/refman/8.0/en/optimization.html", 6),
    ],
    "Troubleshooting": [
        ("The Linux command line for beginners (Ubuntu docs)",
         "https://ubuntu.com/tutorials/command-line-for-beginners", 3),
        ("Microsoft Learn training", _MS_TRAINING, 6),
    ],
    "Hardware Support": [
        ("CS50's Understanding Technology", "https://cs50.harvard.edu/technology/", 12),
        ("Raspberry Pi documentation (official)", "https://www.raspberrypi.com/documentation/", 5),
    ],
    "Customer Service": [
        ("Khan Academy: College, careers, and more", _KHAN_CAREERS, 3),
        ("Microsoft Learn training", _MS_TRAINING, 6),
    ],
}


# --------------------------------------------------------------------------- builders

def role_id(name: str) -> str:
    """'UI/UX Designer' -> 'ui-ux-designer'."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def build_roles() -> list[dict]:
    roles = []
    for name, core, preferred in ROLES:
        skills = [_skill(s, "core") for s in core] + [_skill(s, "preferred") for s in preferred]
        roles.append({"id": role_id(name), "name": name, "skills": skills})
    return roles


def _skill(name: str, requirement: str) -> dict:
    return {"name": name, "category": CATEGORIES[name], "weight": WEIGHTS[requirement], "requirement": requirement}


def build_aliases() -> dict[str, list[str]]:
    return {name: list(aliases) for name, aliases in ALIASES.items()}


def build_resources() -> dict[str, list[dict]]:
    return {
        name: [{"title": title, "url": url, "hours": hours} for title, url, hours in items]
        for name, items in RESOURCES.items()
    }


def role_skill_names(roles: list[dict]) -> set[str]:
    return {s["name"] for role in roles for s in role["skills"]}


def demo_match_pct(roles: list[dict], cv_skills: list[str] = DEMO_CV_SKILLS, role_name: str = DEMO_ROLE) -> float:
    """Weight-based exact-name match, the same arithmetic as matcher.match without embeddings."""
    role = next(r for r in roles if r["name"] == role_name)
    have = {s.lower() for s in cv_skills}
    total = sum(s["weight"] for s in role["skills"])
    gained = sum(s["weight"] for s in role["skills"] if s["name"].lower() in have)
    return round(100.0 * gained / total, 1)


def check(roles: list[dict], aliases: dict[str, list[str]], resources: dict[str, list[dict]]) -> list[str]:
    """Return a list of problems with the tables (empty when everything is consistent)."""
    problems: list[str] = []
    names = role_skill_names(roles)
    lower_names = {n.lower(): n for n in names}

    if len({r["id"] for r in roles}) != len(roles):
        problems.append("duplicate role ids")
    for role in roles:
        skills = [s["name"] for s in role["skills"]]
        if not 10 <= len(skills) <= 20:
            problems.append(f"{role['name']}: {len(skills)} skills (want 10-20)")
        if len(set(skills)) != len(skills):
            problems.append(f"{role['name']}: duplicate skills")
    if len(lower_names) != len(names):
        problems.append("two spellings of the same skill differ only by case")
    for name in names:
        if CATEGORIES[name] not in CATEGORY_NAMES:
            problems.append(f"{name}: bad category {CATEGORIES[name]}")
        if not resources.get(name):
            problems.append(f"{name}: no resources")
        elif len(resources[name]) > 3:
            problems.append(f"{name}: more than 3 resources")

    seen_alias: dict[str, str] = {}
    for canonical_name, items in aliases.items():
        if canonical_name not in names:
            problems.append(f"alias key {canonical_name!r} is not a role skill")
        for alias in items:
            key = alias.lower()
            owner = lower_names.get(key)
            if owner is not None and owner != canonical_name:
                problems.append(f"alias {alias!r} of {canonical_name} is the canonical name {owner!r}")
            if key in seen_alias and seen_alias[key] != canonical_name:
                problems.append(f"alias {alias!r} maps to both {seen_alias[key]} and {canonical_name}")
            seen_alias[key] = canonical_name

    pct = demo_match_pct(roles)
    low, high = DEMO_MATCH_RANGE
    if not low <= pct <= high:
        problems.append(f"demo CV matches {DEMO_ROLE} at {pct}% (want {low}-{high})")
    return problems


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="validate the tables and print stats; write nothing")
    parser.add_argument("--out", type=Path, default=DATA_DIR, help="output directory (default: data/)")
    args = parser.parse_args(argv)

    roles, aliases, resources = build_roles(), build_aliases(), build_resources()
    problems = check(roles, aliases, resources)
    alias_count = sum(len(v) for v in aliases.values())
    print(f"{len(roles)} roles, {len(role_skill_names(roles))} distinct skills, "
          f"{len(aliases)} alias groups ({alias_count} aliases), {len(resources)} skills with resources")
    print(f"demo CV vs {DEMO_ROLE}: {demo_match_pct(roles)}%")
    for problem in problems:
        print(f"PROBLEM: {problem}", file=sys.stderr)
    if problems:
        return 1
    if args.check:
        return 0

    write_json(args.out / "roles.json", roles)
    write_json(args.out / "skill_aliases.json", aliases)
    write_json(args.out / "resources.json", resources)
    print(f"wrote roles.json, skill_aliases.json, resources.json to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
