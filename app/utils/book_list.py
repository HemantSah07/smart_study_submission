"""
BOOK_LIST: Curated book recommendations aligned to Nepal's CDC/NEB curriculum
Keys are subject names matching SUBJECT_MAP. Each entry has title, author,
publisher, and a Google Books search URL.
"""

BOOK_LIST = {
    # ── Class 8–10 Core ───────────────────────────────────────────────────────
    "Nepali": [
        {"title": "Nawa Nepali Byakaran", "author": "Balkrishna Pokhrel", "publisher": "Sajha Prakashan", "url": "https://www.google.com/search?q=Nawa+Nepali+Byakaran+book"},
        {"title": "Nepali Sahitya Sanchayan", "author": "Parijat", "publisher": "Ekta Books", "url": "https://www.google.com/search?q=Nepali+Sahitya+book+CDC"},
    ],
    "English": [
        {"title": "Oxford English Grammar Course", "author": "Michael Swan", "publisher": "Oxford University Press", "url": "https://www.google.com/search?q=Oxford+English+Grammar+Course+Swan"},
        {"title": "Communicative English for Secondary", "author": "CDC Nepal", "publisher": "CDC/Janak Education", "url": "https://www.google.com/search?q=Communicative+English+CDC+Nepal+secondary"},
    ],
    "Mathematics": [
        {"title": "Mathematics Grade 10", "author": "R.M. Shrestha", "publisher": "Sunlight Publication", "url": "https://www.google.com/search?q=Mathematics+Grade+10+Nepal+CDC"},
        {"title": "A Foundation Course in Mathematics", "author": "S.K. Shrestha", "publisher": "Heritage Publishers", "url": "https://www.google.com/search?q=Foundation+Course+Mathematics+Nepal"},
    ],
    "Optional Mathematics": [
        {"title": "Optional Mathematics Grade 9-10", "author": "Lekhnath Sharma", "publisher": "Vidhyarthi Pustak Bhandar", "url": "https://www.google.com/search?q=Optional+Mathematics+Grade+10+Nepal"},
    ],
    "Science and Technology": [
        {"title": "Science and Technology Grade 9", "author": "Ministry of Education", "publisher": "Janak Education", "url": "https://www.google.com/search?q=Science+Technology+Grade+9+Nepal+CDC"},
        {"title": "Exploring Science", "author": "Dr. Bal Krishana Sharma", "publisher": "Buddha Publication", "url": "https://www.google.com/search?q=Exploring+Science+Nepal+secondary"},
    ],
    "Social Studies": [
        {"title": "Social Studies Grade 10", "author": "CDC Nepal", "publisher": "Janak Education", "url": "https://www.google.com/search?q=Social+Studies+Grade+10+Nepal+CDC"},
    ],
    "Social Studies and Population Education": [
        {"title": "Social Studies and Population Education Grade 8", "author": "CDC Nepal", "publisher": "Janak Education", "url": "https://www.google.com/search?q=Social+Studies+Population+Education+Grade+8+Nepal"},
    ],
    "Environment Population and Health": [
        {"title": "EPH Grade 10", "author": "CDC Nepal", "publisher": "Ekta Books", "url": "https://www.google.com/search?q=Environment+Population+Health+Grade+10+Nepal"},
    ],
    "Computer Science": [
        {"title": "Computer Science Grade 9-10", "author": "Binod Thapalia", "publisher": "Quest Publication", "url": "https://www.google.com/search?q=Computer+Science+Grade+10+Nepal+CDC"},
        {"title": "ICT Foundation for Schools", "author": "S.K. Basnet", "publisher": "Asia Publication", "url": "https://www.google.com/search?q=ICT+Foundation+Schools+Nepal"},
    ],
    "Health, Physical and Creative Arts": [
        {"title": "Health and Physical Education Grade 8", "author": "CDC Nepal", "publisher": "Janak Education", "url": "https://www.google.com/search?q=Health+Physical+Creative+Arts+Grade+8+Nepal"},
    ],
    "Health and Physical Education": [
        {"title": "Health and Physical Education Grade 9", "author": "CDC Nepal", "publisher": "Janak Education", "url": "https://www.google.com/search?q=Health+Physical+Education+Grade+9+Nepal"},
    ],
    "Moral Education": [
        {"title": "Moral Education and Social Values", "author": "CDC Nepal", "publisher": "Janak Education", "url": "https://www.google.com/search?q=Moral+Education+Grade+8+Nepal"},
    ],
    "Accountancy": [
        {"title": "Accountancy Grade 11-12", "author": "S.P. Koirala", "publisher": "Asmita Books", "url": "https://www.google.com/search?q=Accountancy+Grade+11+Nepal+NEB"},
        {"title": "Financial Accounting", "author": "Tulsi Ram Pandey", "publisher": "Taleju Prakashan", "url": "https://www.google.com/search?q=Financial+Accounting+Nepal+Grade+12"},
    ],
    "Economics": [
        {"title": "Economics Grade 11-12", "author": "Shankar Prasad Mainali", "publisher": "Asmita Books", "url": "https://www.google.com/search?q=Economics+Grade+11+Nepal+NEB"},
        {"title": "Economics Principles and Applications", "author": "R.P. Koirala", "publisher": "Heritage Publishers", "url": "https://www.google.com/search?q=Economics+principles+applications+Nepal"},
    ],
    "Business Studies": [
        {"title": "Business Studies Grade 11-12", "author": "Ramji Dhakal", "publisher": "Asmita Books", "url": "https://www.google.com/search?q=Business+Studies+Grade+11+Nepal"},
    ],
    "Finance and Accounting": [
        {"title": "Finance and Accounting Grade 11", "author": "B.B. Karki", "publisher": "Sunlight Publication", "url": "https://www.google.com/search?q=Finance+Accounting+Grade+11+Nepal"},
    ],

    # ── Class 11–12 Science ────────────────────────────────────────────────────
    "Physics": [
        {"title": "Principles of Physics", "author": "Ayam Dhakal", "publisher": "Asmita Books", "url": "https://www.google.com/search?q=Principles+Physics+Grade+11+Nepal+NEB"},
        {"title": "University Physics", "author": "Young & Freedman", "publisher": "Pearson", "url": "https://www.google.com/search?q=Young+Freedman+University+Physics"},
    ],
    "Chemistry": [
        {"title": "Chemistry Grade 11-12", "author": "P.P. Upadhyay", "publisher": "Asmita Books", "url": "https://www.google.com/search?q=Chemistry+Grade+11+Nepal+NEB"},
        {"title": "Concise Inorganic Chemistry", "author": "J.D. Lee", "publisher": "Wiley", "url": "https://www.google.com/search?q=JD+Lee+Inorganic+Chemistry"},
    ],
    "Biology": [
        {"title": "Biology Grade 11-12", "author": "Naba Raj Dhakal", "publisher": "Asmita Books", "url": "https://www.google.com/search?q=Biology+Grade+11+Nepal+NEB"},
        {"title": "Campbell Biology", "author": "Jane Reece", "publisher": "Pearson", "url": "https://www.google.com/search?q=Campbell+Biology+textbook"},
    ],

    # ── Class 11–12 Humanities ────────────────────────────────────────────────
    "History": [
        {"title": "History of Nepal", "author": "Baburam Acharya", "publisher": "Mandala Publication", "url": "https://www.google.com/search?q=History+Nepal+Baburam+Acharya"},
        {"title": "World History Grade 11-12", "author": "NEB Textbook", "publisher": "Janak Education", "url": "https://www.google.com/search?q=World+History+Grade+11+Nepal+NEB"},
    ],
    "Geography": [
        {"title": "Geography Grade 11-12", "author": "Krishna P. Bhattarai", "publisher": "Asmita Books", "url": "https://www.google.com/search?q=Geography+Grade+11+Nepal+NEB"},
    ],
    "Political Science": [
        {"title": "Political Science Grade 11-12", "author": "Bishwakanta Mainali", "publisher": "Ratna Pustak Bhandar", "url": "https://www.google.com/search?q=Political+Science+Grade+11+Nepal"},
    ],
    "Sociology": [
        {"title": "Sociology Grade 11-12", "author": "Roop Narayan Shrestha", "publisher": "Asmita Books", "url": "https://www.google.com/search?q=Sociology+Grade+11+Nepal+NEB"},
    ],
    "Social Studies or Mathematics": [
        {"title": "Mathematics Grade 11-12 (Commerce)", "author": "Durga Thapa", "publisher": "Asmita Books", "url": "https://www.google.com/search?q=Mathematics+Commerce+Grade+11+Nepal"},
    ],
    "Mathematics or Social Studies": [
        {"title": "Social Studies Grade 12", "author": "CDC Nepal", "publisher": "Janak Education", "url": "https://www.google.com/search?q=Social+Studies+Grade+12+Nepal+NEB"},
    ],

    # ── University ─────────────────────────────────────────────────────────────
    "Object-Oriented Programming": [
        {"title": "Head First Java", "author": "Kathy Sierra", "publisher": "O'Reilly Media", "url": "https://www.google.com/search?q=Head+First+Java+Kathy+Sierra"},
        {"title": "Clean Code", "author": "Robert C. Martin", "publisher": "Prentice Hall", "url": "https://www.google.com/search?q=Clean+Code+Robert+Martin"},
    ],
    "Database Systems": [
        {"title": "Database System Concepts", "author": "Silberschatz, Korth", "publisher": "McGraw-Hill", "url": "https://www.google.com/search?q=Database+System+Concepts+Silberschatz"},
        {"title": "Learning SQL", "author": "Alan Beaulieu", "publisher": "O'Reilly Media", "url": "https://www.google.com/search?q=Learning+SQL+OReilly"},
    ],
    "Computer Networks": [
        {"title": "Computer Networks", "author": "Andrew Tanenbaum", "publisher": "Prentice Hall", "url": "https://www.google.com/search?q=Computer+Networks+Tanenbaum"},
        {"title": "Computer Networking: A Top-Down Approach", "author": "Kurose & Ross", "publisher": "Pearson", "url": "https://www.google.com/search?q=Kurose+Ross+Computer+Networking"},
    ],
    "Operating Systems": [
        {"title": "Operating System Concepts (Dinosaur Book)", "author": "Silberschatz", "publisher": "Wiley", "url": "https://www.google.com/search?q=Operating+System+Concepts+Silberschatz+dinosaur"},
        {"title": "Modern Operating Systems", "author": "Tanenbaum", "publisher": "Pearson", "url": "https://www.google.com/search?q=Modern+Operating+Systems+Tanenbaum"},
    ],
    "Web Application Development": [
        {"title": "Learning Web Design", "author": "Jennifer Robbins", "publisher": "O'Reilly Media", "url": "https://www.google.com/search?q=Learning+Web+Design+Jennifer+Robbins"},
        {"title": "Flask Web Development", "author": "Miguel Grinberg", "publisher": "O'Reilly Media", "url": "https://www.google.com/search?q=Flask+Web+Development+Grinberg"},
    ],
    "Systems Analysis and Design": [
        {"title": "Systems Analysis and Design", "author": "Kendall & Kendall", "publisher": "Pearson", "url": "https://www.google.com/search?q=Systems+Analysis+Design+Kendall"},
    ],
    "Mathematics I": [
        {"title": "Calculus: Early Transcendentals", "author": "James Stewart", "publisher": "Cengage Learning", "url": "https://www.google.com/search?q=Stewart+Calculus+Early+Transcendentals"},
    ],
    "Communication Skills": [
        {"title": "Technical Communication", "author": "Mike Markel", "publisher": "Bedford/St. Martin's", "url": "https://www.google.com/search?q=Technical+Communication+Markel"},
    ],
    "Algorithm Design and Analysis": [
        {"title": "Introduction to Algorithms (CLRS)", "author": "Cormen, Leiserson, Rivest, Stein", "publisher": "MIT Press", "url": "https://www.google.com/search?q=Introduction+Algorithms+CLRS"},
        {"title": "Grokking Algorithms", "author": "Aditya Bhargava", "publisher": "Manning", "url": "https://www.google.com/search?q=Grokking+Algorithms+Bhargava"},
    ],
    "Machine Learning": [
        {"title": "Hands-On Machine Learning with Scikit-Learn", "author": "Aurélien Géron", "publisher": "O'Reilly Media", "url": "https://www.google.com/search?q=Hands-On+Machine+Learning+Geron"},
        {"title": "Pattern Recognition and Machine Learning", "author": "Bishop", "publisher": "Springer", "url": "https://www.google.com/search?q=Bishop+Pattern+Recognition+Machine+Learning"},
    ],
    "Data Mining": [
        {"title": "Data Mining: Concepts and Techniques", "author": "Han, Kamber", "publisher": "Morgan Kaufmann", "url": "https://www.google.com/search?q=Data+Mining+Concepts+Techniques+Han"},
    ],
    "Software Engineering": [
        {"title": "Software Engineering", "author": "Ian Sommerville", "publisher": "Pearson", "url": "https://www.google.com/search?q=Software+Engineering+Sommerville"},
        {"title": "The Pragmatic Programmer", "author": "Hunt & Thomas", "publisher": "Addison-Wesley", "url": "https://www.google.com/search?q=Pragmatic+Programmer+book"},
    ],
    "Cybersecurity": [
        {"title": "CompTIA Security+ Study Guide", "author": "Mike Chapple", "publisher": "Sybex", "url": "https://www.google.com/search?q=CompTIA+Security+Study+Guide"},
        {"title": "The Web Application Hacker's Handbook", "author": "Stuttard & Pinto", "publisher": "Wiley", "url": "https://www.google.com/search?q=Web+Application+Hackers+Handbook"},
    ],
    "Artificial Intelligence": [
        {"title": "Artificial Intelligence: A Modern Approach", "author": "Russell & Norvig", "publisher": "Pearson", "url": "https://www.google.com/search?q=Russell+Norvig+Artificial+Intelligence+Modern+Approach"},
    ],
    "Mobile Application Development": [
        {"title": "Android Programming: The Big Nerd Ranch Guide", "author": "Phillips & Stewart", "publisher": "Big Nerd Ranch", "url": "https://www.google.com/search?q=Android+Programming+Big+Nerd+Ranch"},
        {"title": "Flutter & Dart Cookbook", "author": "Richard Rose", "publisher": "Packt", "url": "https://www.google.com/search?q=Flutter+Dart+Cookbook+Packt"},
    ],
    "Statistics for Computing": [
        {"title": "Statistics for Engineers and Scientists", "author": "William Navidi", "publisher": "McGraw-Hill", "url": "https://www.google.com/search?q=Statistics+Engineers+Scientists+Navidi"},
    ],
    "Machine Learning Advanced": [
        {"title": "Deep Learning", "author": "Goodfellow, Bengio, Courville", "publisher": "MIT Press", "url": "https://www.google.com/search?q=Deep+Learning+Goodfellow+Bengio"},
    ],
    "Computer Vision": [
        {"title": "Computer Vision: Algorithms and Applications", "author": "Richard Szeliski", "publisher": "Springer", "url": "https://www.google.com/search?q=Computer+Vision+Algorithms+Szeliski"},
    ],
    "Cloud Computing": [
        {"title": "Cloud Computing: Concepts, Technology & Architecture", "author": "Erl, Puttini, Mahmood", "publisher": "Prentice Hall", "url": "https://www.google.com/search?q=Cloud+Computing+Concepts+Technology+Erl"},
    ],
    "Natural Language Processing": [
        {"title": "Speech and Language Processing", "author": "Jurafsky & Martin", "publisher": "Pearson", "url": "https://www.google.com/search?q=Speech+Language+Processing+Jurafsky+Martin"},
    ],
    "Research Methods": [
        {"title": "Research Methods for Business Students", "author": "Saunders, Lewis, Thornhill", "publisher": "Pearson", "url": "https://www.google.com/search?q=Research+Methods+Business+Students+Saunders"},
    ],
    "Big Data Analytics": [
        {"title": "Big Data: A Revolution", "author": "Viktor Mayer-Schönberger", "publisher": "Houghton Mifflin", "url": "https://www.google.com/search?q=Big+Data+Revolution+Mayer+Schonberger"},
        {"title": "Learning Spark", "author": "Chambers & Zaharia", "publisher": "O'Reilly Media", "url": "https://www.google.com/search?q=Learning+Spark+OReilly"},
    ],
    "Human Computer Interaction": [
        {"title": "Don't Make Me Think", "author": "Steve Krug", "publisher": "New Riders", "url": "https://www.google.com/search?q=Don't+Make+Me+Think+Steve+Krug"},
    ],
    "Project Management": [
        {"title": "A Guide to the Project Management Body of Knowledge (PMBOK)", "author": "PMI", "publisher": "PMI", "url": "https://www.google.com/search?q=PMBOK+Guide+Project+Management"},
    ],
    "Final Year Project": [
        {"title": "Writing Your Dissertation", "author": "Derek Swetnam", "publisher": "How To Books", "url": "https://www.google.com/search?q=Writing+Your+Dissertation+Swetnam"},
    ],
    "Advanced AI": [
        {"title": "Reinforcement Learning: An Introduction", "author": "Sutton & Barto", "publisher": "MIT Press", "url": "https://www.google.com/search?q=Reinforcement+Learning+Sutton+Barto"},
    ],
    "Entrepreneurship IT": [
        {"title": "The Lean Startup", "author": "Eric Ries", "publisher": "Crown Business", "url": "https://www.google.com/search?q=Lean+Startup+Eric+Ries"},
    ],
    "Distributed Systems": [
        {"title": "Designing Data-Intensive Applications", "author": "Martin Kleppmann", "publisher": "O'Reilly Media", "url": "https://www.google.com/search?q=Designing+Data-Intensive+Applications+Kleppmann"},
    ],
    "Deep Learning": [
        {"title": "Deep Learning with Python", "author": "François Chollet", "publisher": "Manning", "url": "https://www.google.com/search?q=Deep+Learning+Python+Chollet"},
    ],
    "Capstone Project": [
        {"title": "The Craft of Research", "author": "Booth, Colomb, Williams", "publisher": "University of Chicago", "url": "https://www.google.com/search?q=Craft+of+Research+Booth+Colomb"},
    ],
    # ── Master's Level ────────────────────────────────────────────────────────
    "Advanced Machine Learning": [
        {"title": "Pattern Recognition and Machine Learning", "author": "Bishop", "publisher": "Springer", "url": "https://www.google.com/search?q=Bishop+Pattern+Recognition+Machine+Learning"},
    ],
    "Research Methodology": [
        {"title": "Research Design: Qualitative, Quantitative, and Mixed Methods", "author": "John Creswell", "publisher": "SAGE Publications", "url": "https://www.google.com/search?q=Research+Design+Creswell"},
    ],
    "Thesis Writing": [
        {"title": "How to Write a Thesis", "author": "Umberto Eco", "publisher": "MIT Press", "url": "https://www.google.com/search?q=How+to+Write+a+Thesis+Umberto+Eco"},
    ],
    "Advanced Computer Vision": [
        {"title": "Multiple View Geometry in Computer Vision", "author": "Hartley & Zisserman", "publisher": "Cambridge", "url": "https://www.google.com/search?q=Multiple+View+Geometry+Computer+Vision+Hartley"},
    ],
    "Advanced NLP": [
        {"title": "Natural Language Processing with Transformers", "author": "Lewis Tunstall", "publisher": "O'Reilly Media", "url": "https://www.google.com/search?q=NLP+Transformers+Tunstall+OReilly"},
    ],
    "Data Science": [
        {"title": "Python for Data Analysis", "author": "Wes McKinney", "publisher": "O'Reilly Media", "url": "https://www.google.com/search?q=Python+Data+Analysis+Wes+McKinney"},
        {"title": "The Data Science Handbook", "author": "Field Cady", "publisher": "Wiley", "url": "https://www.google.com/search?q=Data+Science+Handbook+Field+Cady"},
    ],
}

# ── Career pathways per study level / stream ──────────────────────────────────
CAREER_PATHWAYS = {
    "Class 8": [
        {"title": "Secondary Education (Class 9-10)", "icon": "fa-school", "desc": "Focus on building strong foundations in core subjects before SEE.", "color": "#3b82f6"},
        {"title": "Talent Development Programs", "icon": "fa-star", "desc": "Participate in olympiads, science fairs, and coding competitions.", "color": "#8b5cf6"},
    ],
    "Class 9": [
        {"title": "SEE Board Exam Preparation", "icon": "fa-graduation-cap", "desc": "Prepare rigorously for Nepal's SEE (Secondary Education Examination).", "color": "#3b82f6"},
        {"title": "Career Exploration", "icon": "fa-compass", "desc": "Explore science, management, and humanities streams for Class 11.", "color": "#06b6d4"},
    ],
    "Class 10 (SEE)": [
        {"title": "Science Stream (Class 11)", "icon": "fa-flask", "desc": "Gateway to engineering, medicine, and tech careers.", "color": "#10b981"},
        {"title": "Management Stream (Class 11)", "icon": "fa-chart-pie", "desc": "Foundation for business, accounting, and economics.", "color": "#f59e0b"},
        {"title": "Humanities Stream (Class 11)", "icon": "fa-landmark", "desc": "Prepares for law, journalism, social work, and civil services.", "color": "#a855f7"},
    ],
    "Class 11 - Science Stream": [
        {"title": "Engineering (BE/B.Tech)", "icon": "fa-cogs", "desc": "Computer, Civil, Electrical, Mechanical at IOE/CTEVT/private colleges.", "color": "#3b82f6"},
        {"title": "Medicine (MBBS/BDS)", "icon": "fa-heartbeat", "desc": "Medical entrance preparation for IOM and private medical colleges.", "color": "#ef4444"},
        {"title": "BSc IT / B.Sc. Computer Science", "icon": "fa-laptop-code", "desc": "Technology careers in software development, data science, AI.", "color": "#8b5cf6"},
    ],
    "Class 12 - Science Stream": [
        {"title": "Engineering Entrance (IOE/CEE)", "icon": "fa-cogs", "desc": "Appear in IOE Entrance or CEE for engineering and medical.", "color": "#3b82f6"},
        {"title": "BSc Computer Science / IT", "icon": "fa-laptop-code", "desc": "University-level computing, AI, and software engineering.", "color": "#8b5cf6"},
        {"title": "BCA / B.Sc. CSIT", "icon": "fa-code", "desc": "Applied computing programs at TU, PU, and private colleges.", "color": "#06b6d4"},
    ],
    "Class 11 - Management Stream": [
        {"title": "BBA / BBS / BBA-Finance", "icon": "fa-briefcase", "desc": "Business and management education at TU-affiliated colleges.", "color": "#f59e0b"},
        {"title": "CA (Chartered Accountancy)", "icon": "fa-calculator", "desc": "Professional accounting path via ICAN Nepal.", "color": "#10b981"},
    ],
    "Class 12 - Management Stream": [
        {"title": "BBA / MBA Pathway", "icon": "fa-briefcase", "desc": "Business administration and management specializations.", "color": "#f59e0b"},
        {"title": "Banking & Finance Career", "icon": "fa-university", "desc": "Nepal Rastra Bank, commercial banking, MFI careers.", "color": "#3b82f6"},
        {"title": "Chartered Accountancy (ICAN)", "icon": "fa-calculator", "desc": "Nepal's CA program — one of the top professional credentials.", "color": "#10b981"},
    ],
    "Class 11 - Humanities Stream": [
        {"title": "Law (LLB)", "icon": "fa-balance-scale", "desc": "Legal education and advocacy at TU Law Campus.", "color": "#a855f7"},
        {"title": "Civil Services / Lok Sewa", "icon": "fa-building", "desc": "Prepare for PSC exams and Nepal government services.", "color": "#3b82f6"},
        {"title": "Journalism / Mass Communication", "icon": "fa-newspaper", "desc": "Media, digital content, and broadcasting careers.", "color": "#f59e0b"},
    ],
    "Class 12 - Humanities Stream": [
        {"title": "Law (LLB/BA-LLB)", "icon": "fa-balance-scale", "desc": "5-year integrated LLB or 3-year LLB after BA.", "color": "#a855f7"},
        {"title": "Civil Services (PSC)", "icon": "fa-building", "desc": "Nepal Public Service Commission — officer and administrative roles.", "color": "#3b82f6"},
        {"title": "Sociology / Psychology Research", "icon": "fa-users", "desc": "Academic and NGO research, counselling, and development sectors.", "color": "#06b6d4"},
    ],
    "University Year 1": [
        {"title": "Software Developer", "icon": "fa-code", "desc": "Full-stack, backend, mobile development roles across Nepal and abroad.", "color": "#3b82f6"},
        {"title": "Internship & Industrial Training", "icon": "fa-industry", "desc": "Leverage Year 1 skills in web projects, startup internships.", "color": "#10b981"},
    ],
    "University Year 2": [
        {"title": "Data Analyst / ML Engineer", "icon": "fa-chart-bar", "desc": "Data analytics roles with Python, SQL, and ML pipelines.", "color": "#8b5cf6"},
        {"title": "Cybersecurity Analyst", "icon": "fa-shield-alt", "desc": "Security roles at banks, ISPs, and government agencies.", "color": "#ef4444"},
        {"title": "Open Source Contributions", "icon": "fa-github", "desc": "Build a portfolio through GitHub projects and hackathons.", "color": "#64748b"},
    ],
    "University Year 3": [
        {"title": "AI / Machine Learning Engineer", "icon": "fa-brain", "desc": "Advanced ML, NLP, and computer vision applications.", "color": "#8b5cf6"},
        {"title": "Cloud Engineer (AWS/GCP/Azure)", "icon": "fa-cloud", "desc": "Cloud infrastructure and DevOps for modern applications.", "color": "#06b6d4"},
        {"title": "Research Assistant / Publication", "icon": "fa-flask", "desc": "Publish papers, assist faculty research, prepare for Master's.", "color": "#f59e0b"},
    ],
    "University Year 4": [
        {"title": "Graduate Software Engineer", "icon": "fa-laptop-code", "desc": "Senior roles at tech companies and startups in Nepal and abroad.", "color": "#3b82f6"},
        {"title": "Master's Program (MSc / MPhil)", "icon": "fa-graduation-cap", "desc": "Research-oriented graduate education in CS, AI, or Data Science.", "color": "#a855f7"},
        {"title": "Tech Entrepreneurship", "icon": "fa-rocket", "desc": "Start your own SaaS or product company with capstone knowledge.", "color": "#f59e0b"},
    ],
    "Master's Level": [
        {"title": "PhD / Doctoral Research", "icon": "fa-microscope", "desc": "Academic and research careers at universities and R&D labs.", "color": "#a855f7"},
        {"title": "Senior Data Scientist / AI Researcher", "icon": "fa-brain", "desc": "High-impact roles at tech giants, research labs, or UN agencies.", "color": "#8b5cf6"},
        {"title": "University Lecturer / Professor", "icon": "fa-chalkboard-teacher", "desc": "Teaching and research at TU, KU, PU, or abroad.", "color": "#10b981"},
    ],
}

# ── Next level mapping ─────────────────────────────────────────────────────────
NEXT_LEVEL_MAP = {
    "Class 8":                      "Class 9",
    "Class 9":                      "Class 10 (SEE)",
    "Class 10 (SEE)":               "Class 11 - Science Stream",
    "Class 11 - Science Stream":    "Class 12 - Science Stream",
    "Class 11 - Management Stream": "Class 12 - Management Stream",
    "Class 11 - Humanities Stream": "Class 12 - Humanities Stream",
    "Class 12 - Science Stream":    "University Year 1",
    "Class 12 - Management Stream": "University Year 1",
    "Class 12 - Humanities Stream": "University Year 1",
    "University Year 1":            "University Year 2",
    "University Year 2":            "University Year 3",
    "University Year 3":            "University Year 4",
    "University Year 4":            "Master's Level",
    "Master's Level":               None,
}

# ── 4-Week progression planner templates per level ────────────────────────────
PROGRESSION_PLAN = {
    "default": [
        {"week": 1, "title": "Foundation Review",    "icon": "fa-seedling",    "color": "#3b82f6",
         "tasks": ["Review core subject definitions and formulas", "Complete 1 past paper per subject", "Set up a daily 2-hour study block", "Identify your 3 weakest topics"]},
        {"week": 2, "title": "Deep Concept Drilling", "icon": "fa-dumbbell",   "color": "#8b5cf6",
         "tasks": ["Study each weak topic for 45 min sessions", "Generate 10 flashcards per topic", "Watch 2 video tutorials per weak subject", "Attempt MCQ sets (20 questions/day)"]},
        {"week": 3, "title": "Practice & Application", "icon": "fa-pencil-alt","color": "#f59e0b",
         "tasks": ["Complete 2 full mock exams under timed conditions", "Review all wrong answers in detail", "Write revision summaries for each chapter", "Form a study group or peer review session"]},
        {"week": 4, "title": "Final Revision & Exam Ready", "icon": "fa-rocket","color": "#10b981",
         "tasks": ["Speed-review all flashcards and revision notes", "Simulate exam conditions (full paper, timed)", "Rest adequately — avoid cramming 48h before", "Review mark scheme and ensure all formats understood"]},
    ],
    "Class 8": [
        {"week": 1, "title": "SEE Foundation Prep",  "icon": "fa-seedling",   "color": "#3b82f6",
         "tasks": ["Revise Math formulas: area, algebra, percentage", "Practice English grammar — tenses and comprehension", "Map all Science chapters to CDC syllabus", "Set a daily study routine of 1.5 hours"]},
        {"week": 2, "title": "Subject Deep-Dive",    "icon": "fa-book-open",  "color": "#8b5cf6",
         "tasks": ["Solve past Grade 9 Math papers", "Practice Science diagrams: cell, plant, human body", "Write 3 Nepali essays: narrative, descriptive, opinion", "Review Computer Science: hardware, software, MS Office"]},
        {"week": 3, "title": "MCQ & Application",   "icon": "fa-pencil-alt", "color": "#f59e0b",
         "tasks": ["Complete 20 Social Studies MCQs daily", "Practice Optional Math word problems", "Mock exam: full Math paper under time limit", "Peer-teach one topic to a classmate"]},
        {"week": 4, "title": "SEE Simulation",      "icon": "fa-graduation-cap","color":"#10b981",
         "tasks": ["Full mock SEE exam — all subjects", "Review all red (wrong) answers", "Prepare cheat-sheet summaries for Science & Math", "Rest well and maintain confidence"]},
    ],
}
