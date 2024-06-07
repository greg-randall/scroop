open_ai_key = ""


threads = 8


search_sites = [ 
    'https://jobs.chronicle.com/jobsrss/?countrycode=US&keywords=',
    'https://careers.insidehighered.com/jobsrss/?countrycode=US&keywords=',
    'https://www.timeshighereducation.com/unijobs/jobsrss/?keywords=',
    'https://main.hercjobs.org/jobs/?display=rss&keywords=',
    'https://www.linkedin.com/jobs/search/?keywords=',
    'https://academiccareers.com/rss/?q=',
    'https://www.higheredjobs.com/search/advanced_action.cfm?Keyword=',
    'https://academicpositions.com/find-jobs?search=',
    'https://academicjobsonline.org/ajo?action=joblist&args=-0-0-&send=Go&id=',
    'https://finearts.academickeys.com/seeker_search.php?q=' #this site has several other categories -- see this page for a list https://www.academickeys.com/all/choose_discipline.php. seems like you just swap the subdomain from 'finearts' to 'law'.
]


search_words = [
    '"web developer"',
    '"web designer"',
    'mongodb',
    'javascript',
    ]


bullet_resume = """Education:
B.S. Computer Science, University of Georgia

Skills:
JavaScript, HTML, CSS, React.js, Node.js, Angular.js, MongoDB, AWS, Java

Career Objective:
Experienced software engineer seeking challenging opportunities for skill development.

Work Experience:
Web Developer, Squarespace:
Coached junior designers in accessibility standards.
Led transition to AWS, reducing costs and increasing load speeds.
Created documentation on React.js and Node.js best practices.
Addressed lead prioritization with Websocket connectivity.

Web Designer, Coca-Cola:
Designed mockups and wireframes for product landing pages.
Ensured accessibility and responsiveness for user experience consistency.
Developed user experience for data analytics using React components.
Collaborated on efficiency-improving tool.

Web Development Intern, SiriusXM:
Enhanced user satisfaction with modern JavaScript frameworks.
Developed Node.js code adhering to industry standards.
Gained proficiency in design patterns and concurrency.
Utilized React.js and Angular.js to increase audience engagement."""