"""The demo's fictional employers and their postings.

Every company is invented and every address uses a reserved example domain
(``FICTIONAL_DOMAINS``); a test fails on any other name or domain.
"""

# Reserved for documentation and tests (RFC 2606, RFC 6761): they never reach a real site.
FICTIONAL_DOMAINS = ("example.test", "example.org", "example.com", "example")

POSTINGS = {
    "voltline": (
        "Voltline Grid Analytics turns measurements from electricity networks into forecasts "
        "that grid operators use to plan their day. Our grid data team of seven engineers runs "
        "the services that receive meter and substation readings, check them and serve them "
        "to forecasting models and to our customers' control rooms. We work from Amsterdam, with "
        "two office days a week.\n\n"
        "As a senior backend engineer you will design and run Python services and APIs for "
        "measurement data, improve the reliability and latency of our ingestion path, and "
        "help the team operate what it builds, including a shared on-call rotation. You have "
        "five or more years of backend development with Python and SQL, experience running "
        "services in containers on Linux, and a habit of measuring before you optimize. "
        "Experience with time-series data or the energy sector is welcome but not required. "
        "Fluent English is required. The salary range is EUR 80,000 to 95,000 a year."
    ),
    "carbon": (
        "The Carbon Ledger Foundation is a nonprofit that publishes open emissions data for "
        "more than 4,000 companies. Researchers, journalists and regulators rely on our "
        "datasets and our public API. We are a remote team of 25 across Europe, with a small "
        "engineering group of five.\n\n"
        "You will build the services behind our public API, keep our data pipelines correct "
        "and reproducible, and work with our research team on new datasets. You will review "
        "code, write clear documentation and share on-call duty for the API. We look for "
        "three or more years of backend experience with Python, good SQL, experience with "
        "public APIs and an interest in climate data. Please include a link to a public code "
        "sample with your application. Fluent English is required. Applications close at "
        "the end of next week."
    ),
    "tessellate": (
        "Tessellate Maps builds geospatial software for public transport companies and city "
        "planners in Spain and Italy. Our backend team in Barcelona maintains the APIs "
        "that serve routes, stops and timetables to web and mobile applications used by "
        "around two million travelers each month.\n\n"
        "As a backend engineer you will develop new endpoints for our geospatial APIs, "
        "improve query performance on PostgreSQL and take part in design reviews. You will "
        "work closely with our customers' technical teams. We look for solid experience with "
        "Python and SQL, practical knowledge of Docker and Linux, and care for API design. "
        "Experience with PostGIS is a plus. Fluent Italian and English are required, as "
        "many of our customers work in Italian. We offer a hybrid model with three office "
        "days a week in Barcelona."
    ),
    "lumacare": (
        "Lumacare Health makes software that helps hospitals in Ireland and the United Kingdom plan "
        "patient care across wards. Our patient platform team owns the services that store "
        "care plans and synchronize them with hospital systems. The team has six engineers "
        "and a product manager and works from Dublin, with flexible office days.\n\n"
        "You will build and operate backend services in Python, design APIs used by our "
        "web application and by hospital integrations, and help us improve observability "
        "across the platform. You have at least four years of backend experience, are "
        "comfortable with SQL and asynchronous workers, and you write tests and "
        "documentation as part of your work. Experience with healthcare data standards is a "
        "plus. Fluent English is required."
    ),
    "larchmont": (
        "The data platform team of Larchmont Bank builds the shared services that our "
        "analysts and risk teams use to load, check and query data. We are twelve engineers "
        "in Lisbon and work closely with the bank's security and compliance teams.\n\n"
        "As a data platform engineer you will develop Python services that move data "
        "between our core systems and the analytics platform, build self-service APIs for "
        "data access, and automate deployments. You will also help analysts write efficient "
        "SQL. We look for experience with Python, SQL and APIs, familiarity with Docker and "
        "Linux, and a careful approach to change in a regulated environment. Experience in "
        "financial services is welcome. Fluent English is required. We offer a hybrid model, "
        "a yearly training budget and a pension plan above the legal minimum."
    ),
    "freightwise": (
        "Freightwise is a logistics scale-up that matches freight with available trucks "
        "across Europe. Our routing and pricing services handle about 30,000 shipments a "
        "day. The backend team works remotely within Europe and meets in person twice a "
        "year.\n\n"
        "As a Python backend engineer you will design and build APIs for carriers and "
        "shippers, move slow synchronous work to asynchronous workers, and improve how we "
        "deploy and roll back services. You have three or more years of experience with "
        "Python in production, good knowledge of SQL, and experience with Docker and "
        "continuous delivery. You like to make operations simpler for the whole team. "
        "Fluent English is required. We offer a remote contract within Europe, a home "
        "office budget and four weeks of paid holiday plus public holidays."
    ),
    "quayside": (
        "Quayside Payments provides payment processing for online shops in the United Kingdom "
        "and Ireland. Our payments API team builds the endpoints that merchants integrate "
        "with and keeps them fast and available around the clock.\n\n"
        "You will develop new API features, improve error handling and idempotency, and "
        "take part in incident reviews. We look for four or more years of backend "
        "experience, strong SQL, experience with REST APIs and an interest in payments. "
        "Experience with Kotlin or Java is a plus. Fluent English is required. The role is "
        "based in London with two days of remote work a week, and we sponsor work visas."
    ),
    "kelpie": (
        "Kelpie Labs builds developer tools for teams that run Python services: a deployment "
        "dashboard, health checks and release notes generated from commits. We are a fully "
        "remote company of 40 people, based in Toronto, with colleagues across Canada and Europe.\n\n"
        "As a senior Python engineer you will work on our deployment workflow product, from "
        "the API to the background workers that run checks and rollbacks. You will help "
        "shape our technical direction and mentor colleagues. We look for strong Python "
        "experience, a good understanding of Linux and containers, and experience designing "
        "reliable deployment or release processes. Experience with TypeScript is a plus. "
        "Fluent English is required. We hire as contractors outside Canada and offer "
        "flexible hours and a learning budget."
    ),
    "meridian": (
        "Meridian Insurance Group is modernizing how its brokers and customers access policy "
        "data. Our new data APIs team in Berlin replaces nightly file exports with APIs that "
        "partners can call directly.\n\n"
        "You will design and build those APIs in Python, model data in SQL and work with "
        "architects on security and access control. You will also help colleagues from "
        "other teams adopt the new APIs. We look for experience with Python, SQL and REST "
        "APIs and an interest in clear documentation. Experience in insurance is not needed. "
        "Fluent English is required. The role is hybrid, with two office days a week in "
        "Berlin, and pays EUR 75,000 to 85,000 a year."
    ),
    "fernhill": (
        "Fernhill Mobility runs a booking platform for shared electric vans in eight European "
        "cities. Our platform team provides the infrastructure and tooling that our product "
        "teams use to ship every day.\n\n"
        "As a platform engineer you will improve our deployment pipelines, run our container "
        "platform on Linux and build internal APIs for service health. You will also take "
        "part in an on-call rotation. We look for experience with Docker, Linux and Python, "
        "and an interest in making developers' work simpler. Experience with Terraform is a "
        "plus. Fluent English is required. The role is remote within Europe."
    ),
    "cobalt": (
        "Cobalt Telecom provides mobile and internet plans to small businesses in "
        "Ireland. The billing team builds the services that rate usage and produce "
        "monthly invoices for 60,000 customers.\n\n"
        "As a software engineer you will develop billing services in Python, improve the "
        "accuracy of our rating rules and work with finance on reports. We look for two or "
        "more years of experience with Python and SQL, care for correctness, and good "
        "communication. Fluent English is required. The role is based in Dublin, with "
        "flexible hours and one remote day a week."
    ),
    "spreeland": (
        "Die Spreeland Energie GmbH versorgt über 200.000 Haushalte in Berlin und Brandenburg "
        "mit Strom und Wärme. Für unser Team Digitale Dienste in Berlin suchen wir eine "
        "Backend-Entwicklerin oder einen Backend-Entwickler.\n\n"
        "Deine Aufgaben: Du entwickelst Dienste in Python für unser Kundenportal, du "
        "betreust Schnittstellen zu unseren Abrechnungssystemen und du arbeitest eng mit "
        "dem Betrieb zusammen. Dein Profil: mehrjährige Erfahrung mit Python und SQL, "
        "Erfahrung mit Docker und Linux, fließend Deutsch (C1) und gute Englischkenntnisse. "
        "Wir bieten flexible Arbeitszeiten, zwei Tage Homeoffice pro Woche und ein "
        "Jobticket für den Nahverkehr."
    ),
    "pixelwright": (
        "Pixelwright Studio is a digital agency that builds websites and web applications "
        "for clients in retail and tourism. We are looking for a frontend engineer to join "
        "our client delivery team in Amsterdam.\n\n"
        "You will build user interfaces in React and TypeScript for client projects, work "
        "with our designers on component libraries and present your work to clients. We "
        "look for three years of experience with React, strong CSS skills and experience "
        "with design systems. Fluent English is required. We offer a hybrid model and a "
        "yearly team trip."
    ),
    "northpeak": (
        "Northpeak Trading builds low-latency trading systems for energy markets. Our "
        "backend group in London is growing and we are looking for a staff backend "
        "engineer.\n\n"
        "You will lead the design of our order and position services, set engineering "
        "standards and mentor engineers across three teams. We look for eight or more years "
        "of backend experience, deep knowledge of Python or Java, and experience with "
        "trading systems. Fluent English is required. The role is on site in London, five "
        "days a week."
    ),
    "saltmarsh": (
        "Saltmarsh Analytics forecasts demand for district heating networks in Denmark and "
        "Sweden. Our forecasting platform team of eight engineers works from Copenhagen, with "
        "two office days a week.\n\n"
        "As a backend engineer you will build the Python services that feed weather and "
        "consumption data to our models and serve forecasts to network operators. We look "
        "for four or more years of backend experience with Python and SQL and experience "
        "with asynchronous workers. Fluent English is required; Danish is not. The salary "
        "range is DKK 620,000 to 700,000 a year, and we help with relocation."
    ),
    "lindgren": (
        "Lindgren Climate Tech helps manufacturers measure the emissions of their supply "
        "chains. Our team in Stockholm builds the APIs that suppliers use to report data.\n\n"
        "You will design APIs in Python, keep imports of supplier data correct and help the "
        "team run its services. We look for three or more years of backend experience, good "
        "SQL and clear writing. Fluent English is required. The role is hybrid in Stockholm "
        "and pays SEK 650,000 to 720,000 a year."
    ),
}

# New jobs: key, title, company, location, source, days ago, salary (currency, low, high)
# or None, and the posting's two paragraphs.
NEW_JOBS = (
    (
        "ferrous-sre",
        "Site Reliability Engineer",
        "Ferrous Cloud",
        "Rotterdam, Netherlands (hybrid)",
        "search",
        0.2,
        ("EUR", 70000, 85000),
        (
            "Ferrous Cloud runs managed databases for 3,000 small companies across Europe. Our "
            "reliability team of six keeps them available and fast."
        ),
        (
            "You will automate our fleet operations in Python, improve alerting and take part in "
            "on-call. We look for experience with Linux, containers and PostgreSQL. Fluent "
            "English is required."
        ),
    ),
    (
        "kestrel-clinical-data",
        "Python Developer, Clinical Data",
        "Kestrel Health Data",
        "Utrecht, Netherlands (hybrid)",
        "search",
        0.6,
        ("EUR", 60000, 72000),
        (
            "Kestrel Health Data prepares anonymized clinical data for university research "
            "groups. We are a team of fifteen in Utrecht."
        ),
        (
            "You will build Python pipelines that check, link and anonymize hospital data, and "
            "APIs that researchers use to request it. Good SQL and care for privacy are required. "
            "Fluent English is required; Dutch is a plus."
        ),
    ),
    (
        "tidewater-backend",
        "Backend Engineer",
        "Tidewater Energy Software",
        "Aberdeen, United Kingdom (hybrid)",
        "europe",
        1.2,
        ("GBP", 65000, 78000),
        (
            "Tidewater Energy Software plans maintenance for offshore wind farms. Our backend "
            "team builds the services behind the planning tools of 40 wind farm operators."
        ),
        (
            "You will develop Python APIs, model maintenance schedules in SQL and work with our "
            "product designers. Four years of backend experience are required. We sponsor work "
            "visas."
        ),
    ),
    (
        "gullwing-bookings",
        "Backend Engineer, Bookings",
        "Gullwing Travel",
        "Lisbon, Portugal (hybrid)",
        "europe",
        1.5,
        ("EUR", 50000, 62000),
        (
            "Gullwing Travel sells ferry and coach tickets in southern Europe. Our bookings team "
            "in Lisbon handles about 20,000 bookings a day."
        ),
        (
            "You will improve our booking APIs, make payment flows idempotent and reduce failed "
            "bookings. We look for experience with Python or Go, SQL and message queues. Fluent "
            "English is required."
        ),
    ),
    (
        "marisol-senior-python",
        "Senior Python Engineer",
        "Marisol Fintech",
        "Madrid, Spain (hybrid)",
        "europe",
        2.1,
        ("EUR", 62000, 75000),
        (
            "Marisol Fintech offers invoice financing to small companies in Spain and Portugal. "
            "Our engineering team of 30 works from Madrid."
        ),
        (
            "You will design the services that score invoices and move funds, review code and "
            "mentor two engineers. We look for six years of Python, strong SQL and experience in "
            "a regulated environment. Fluent English is required; Spanish is a plus."
        ),
    ),
    (
        "bramble-platform",
        "Platform Engineer",
        "Bramble Commerce",
        "Manchester, United Kingdom (hybrid)",
        "europe",
        2.4,
        ("GBP", 70000, 82000),
        (
            "Bramble Commerce builds online shops for independent grocers. Our platform team "
            "gives twelve product teams their pipelines, clusters and observability."
        ),
        (
            "You will run our Kubernetes platform, improve deployments and write internal tools "
            "in Python. Experience with Terraform and a cloud provider is required. Fluent "
            "English is required."
        ),
    ),
    (
        "cinder-data-engineer",
        "Data Engineer",
        "Cinder Analytics",
        "Paris, France (hybrid)",
        "europe",
        2.8,
        ("EUR", 58000, 70000),
        (
            "Cinder Analytics measures the audience of independent podcasts. Our data team in "
            "Paris processes 50 million listening events a day."
        ),
        (
            "You will build batch and streaming pipelines in Python and SQL, keep our metrics "
            "correct and help analysts. Experience with Airflow or a similar scheduler is "
            "welcome. Fluent English is required."
        ),
    ),
    (
        "velvetleaf-learning",
        "Backend Engineer, Learning Platform",
        "Velvetleaf Learning",
        "Remote, Europe",
        "feed",
        0.9,
        ("EUR", 65000, 78000),
        (
            "Velvetleaf Learning makes a course platform for vocational schools. We are a remote "
            "company of 60 people across Europe."
        ),
        (
            "You will build Python APIs for course content and progress, improve search and help "
            "us split a large application into services. Four years of backend experience are "
            "required. Fluent English is required."
        ),
    ),
    (
        "polder-sensor-data",
        "Software Engineer, Sensor Data",
        "Polder Water Systems",
        "Delft, Netherlands (hybrid)",
        "search",
        1.8,
        ("EUR", 62000, 74000),
        (
            "Polder Water Systems monitors dikes and pumping stations for Dutch water boards. "
            "Our sensor data team receives readings from 12,000 sensors."
        ),
        (
            "You will develop the Python services that store readings and raise alerts, and APIs "
            "for our dashboards. Experience with time-series data is a plus. Fluent English is "
            "required; Dutch is a plus."
        ),
    ),
    (
        "ashgrove-api",
        "API Engineer",
        "Ashgrove Insurance",
        "Brussels, Belgium (hybrid)",
        "europe",
        3.2,
        ("EUR", 64000, 76000),
        (
            "Ashgrove Insurance sells home and travel insurance in Belgium and Luxembourg. Our "
            "API team connects brokers to our policy systems."
        ),
        (
            "You will design and document REST APIs in Python, work on access control and "
            "support brokers' developers. Experience with OpenAPI is welcome. Fluent English is "
            "required; French or Dutch is a plus."
        ),
    ),
    (
        "fjordline-payments",
        "Backend Engineer, Payments",
        "Fjordline Payments",
        "Oslo, Norway (hybrid)",
        "europe",
        3.6,
        ("NOK", 750000, 880000),
        (
            "Fjordline Payments processes card payments for restaurants in the Nordic countries. "
            "Our payments team works from Oslo."
        ),
        (
            "You will build payment APIs, settlement jobs and reconciliation reports. We look for "
            "experience with Python or Kotlin, SQL and payment systems. Fluent English is "
            "required; Norwegian is not."
        ),
    ),
    (
        "lanterna-streaming",
        "Backend Engineer, Streaming",
        "Lanterna Media",
        "Milan, Italy (hybrid)",
        "europe",
        4.1,
        ("EUR", 48000, 60000),
        (
            "Lanterna Media streams regional sports and concerts in Italy. Our backend team in "
            "Milan serves 300,000 viewers on a busy evening."
        ),
        (
            "You will work on our catalog and entitlement APIs in Python and improve how they "
            "behave under load. Fluent Italian and English are required."
        ),
    ),
    (
        "copperleaf-fleet",
        "Python Engineer, Fleet Software",
        "Copperleaf Robotics",
        "Eindhoven, Netherlands",
        "search",
        4.5,
        ("EUR", 65000, 80000),
        (
            "Copperleaf Robotics builds autonomous carts for warehouses. Our fleet software team "
            "assigns tasks to 2,000 carts in 30 warehouses."
        ),
        (
            "You will build the Python services that plan tasks and collect telemetry, and help "
            "us test them against a simulator. Experience with asynchronous Python is required. "
            "Fluent English is required."
        ),
    ),
    (
        "glimmer-live-services",
        "Backend Engineer, Live Services",
        "Glimmer Games",
        "Helsinki, Finland (hybrid)",
        "europe",
        5.0,
        ("EUR", 60000, 72000),
        (
            "Glimmer Games makes puzzle games for phones with two million daily players. Our live "
            "services team runs accounts, events and leaderboards."
        ),
        (
            "You will build backend services in Python and Go and keep them fast during events. "
            "Experience with Redis and PostgreSQL is welcome. Fluent English is required."
        ),
    ),
    (
        "stoneharbor-backend",
        "Backend Engineer",
        "Stoneharbor Logistics",
        "Hamburg, Germany (hybrid)",
        "europe",
        5.4,
        ("EUR", 68000, 80000),
        (
            "Stoneharbor Logistics schedules container transport between ports and inland "
            "terminals. Our engineering team in Hamburg works in English."
        ),
        (
            "You will develop Python APIs for terminal operators and integrate partner systems. "
            "Four years of backend experience and good SQL are required. Fluent English is "
            "required; German is a plus."
        ),
    ),
    (
        "arbor-ledger-senior",
        "Senior Backend Engineer",
        "Arbor Ledger",
        "Vienna, Austria (hybrid)",
        "europe",
        6.0,
        ("EUR", 65000, 78000),
        (
            "Arbor Ledger makes accounting software for associations and clubs in Austria and "
            "Germany. Our backend team has eight engineers."
        ),
        (
            "You will lead the design of our booking and reporting services in Python and mentor "
            "colleagues. Six years of backend experience are required. Fluent English is "
            "required; German is a plus."
        ),
    ),
    (
        "quillstone-python",
        "Python Developer",
        "Quillstone Legal Tech",
        "Remote, United Kingdom",
        "feed",
        1.1,
        ("GBP", 60000, 70000),
        (
            "Quillstone Legal Tech helps law firms find clauses in contracts. We are a remote "
            "team of twenty in the United Kingdom."
        ),
        (
            "You will build the services that import documents and serve search results, in "
            "Python with PostgreSQL. Three years of experience are required. Right to work in "
            "the United Kingdom is required."
        ),
    ),
    (
        "halcyon-ground-segment",
        "Software Engineer, Ground Segment",
        "Halcyon Satellite Data",
        "Toulouse, France (hybrid)",
        "europe",
        2.2,
        ("EUR", 55000, 68000),
        (
            "Halcyon Satellite Data operates small Earth observation satellites. Our ground "
            "segment team receives and processes their images."
        ),
        (
            "You will develop Python services that schedule downloads and process images, and "
            "APIs for our customers. Experience with Linux and containers is required. Fluent "
            "English is required."
        ),
    ),
    (
        "brightmoor-core-apis",
        "Backend Engineer, Core Banking APIs",
        "Brightmoor Bank",
        "Warsaw, Poland (hybrid)",
        "europe",
        3.0,
        ("PLN", 260000, 320000),
        (
            "Brightmoor Bank is a digital bank with 400,000 customers in Poland. Our core banking "
            "APIs team opens the bank's systems to the mobile app and to partners."
        ),
        (
            "You will build and secure APIs in Python and Java and improve their tests. Four "
            "years of backend experience are required. Fluent English is required."
        ),
    ),
    (
        "kiln-data-platform",
        "Data Platform Engineer",
        "Kiln Data",
        "Prague, Czechia (hybrid)",
        "europe",
        3.9,
        ("EUR", 50000, 62000),
        (
            "Kiln Data runs a data platform for online retailers in central Europe. Our team in "
            "Prague maintains the ingestion and query services."
        ),
        (
            "You will build connectors and ingestion jobs in Python and tune queries. Experience "
            "with SQL and a cloud data warehouse is required. Fluent English is required."
        ),
    ),
    (
        "mosswood-carbon",
        "Backend Engineer, Carbon Accounting",
        "Mosswood Climate",
        "Copenhagen, Denmark (hybrid)",
        "feed",
        4.3,
        ("DKK", 600000, 680000),
        (
            "Mosswood Climate calculates the carbon footprint of construction projects. Our "
            "product team of ten works from Copenhagen."
        ),
        (
            "You will build the calculation services and APIs in Python and keep results "
            "traceable to their sources. Three years of backend experience are required. Fluent "
            "English is required."
        ),
    ),
    (
        "silverpine-backend",
        "Backend Engineer",
        "Silverpine Health",
        "Stockholm, Sweden (hybrid)",
        "europe",
        4.8,
        ("SEK", 600000, 700000),
        (
            "Silverpine Health runs video appointments for primary care in Sweden. Our backend "
            "team builds booking and patient record integrations."
        ),
        (
            "You will develop Python services and APIs and work with clinics on integrations. "
            "Experience with healthcare systems is a plus. Fluent English is required."
        ),
    ),
    (
        "tallgrass-senior-backend",
        "Senior Backend Engineer",
        "Tallgrass Analytics",
        "Remote, United States",
        "feed",
        0.4,
        ("USD", 150000, 175000),
        (
            "Tallgrass Analytics forecasts crop yields for farm cooperatives. We are a remote "
            "company across the United States."
        ),
        (
            "You will design Python services for satellite and weather data and mentor two "
            "engineers. Six years of backend experience are required. US work authorization is "
            "required."
        ),
    ),
    (
        "wavecrest-pricing",
        "Backend Engineer, Ride Pricing",
        "Wavecrest Mobility",
        "Singapore",
        "feed",
        2.6,
        ("SGD", 110000, 135000),
        (
            "Wavecrest Mobility runs bike and scooter sharing in five Asian cities. Our pricing "
            "team sets fares and promotions in real time."
        ),
        (
            "You will build pricing services in Python and Go and run experiments with the data "
            "team. Three years of backend experience are required. We sponsor employment passes."
        ),
    ),
    (
        "ironbark-python",
        "Python Engineer",
        "Ironbark Software",
        "Melbourne, Australia (hybrid)",
        "feed",
        3.4,
        ("AUD", 140000, 160000),
        (
            "Ironbark Software makes scheduling software for hospitals in Australia and New "
            "Zealand. Our team of 25 works from Melbourne."
        ),
        (
            "You will develop rostering services and APIs in Python and improve their "
            "performance. Four years of backend experience are required. Australian work rights "
            "are required."
        ),
    ),
    (
        "lumen-lark-search",
        "Backend Engineer, Search",
        "Lumen & Lark",
        "Dublin, Ireland (hybrid)",
        "europe",
        1.4,
        ("EUR", 70000, 82000),
        (
            "Lumen & Lark runs an online marketplace for second-hand books. Our search team "
            "indexes eight million listings."
        ),
        (
            "You will improve indexing and ranking services in Python and measure search "
            "quality. Experience with a search engine such as OpenSearch is welcome. Fluent "
            "English is required."
        ),
    ),
    (
        "pebblebrook-data",
        "Data Engineer",
        "Pebblebrook Insurance",
        "Edinburgh, United Kingdom (hybrid)",
        "europe",
        5.8,
        ("GBP", 55000, 66000),
        (
            "Pebblebrook Insurance offers pet insurance in the United Kingdom. Our data team "
            "builds the warehouse that pricing and claims teams use."
        ),
        (
            "You will build pipelines in Python and SQL and help analysts model claims data. "
            "Three years of experience are required. We sponsor work visas."
        ),
    ),
    (
        "redwing-maintenance-data",
        "Backend Engineer, Maintenance Data",
        "Redwing Aviation Systems",
        "Bilbao, Spain (hybrid)",
        "europe",
        6.3,
        ("EUR", 50000, 60000),
        (
            "Redwing Aviation Systems keeps maintenance records for regional airlines. Our "
            "backend team works from Bilbao."
        ),
        (
            "You will build Python APIs for maintenance records and their audits. Care for "
            "correctness and good SQL are required. Fluent English is required."
        ),
    ),
    (
        "sundial-integrations",
        "Python Engineer, Integrations",
        "Sundial Scheduling",
        "Remote, Europe",
        "feed",
        0.7,
        None,
        (
            "Sundial Scheduling makes appointment software for hair salons and clinics. We are a "
            "remote team of 30 within Europe."
        ),
        (
            "You will build integrations with calendars, payment providers and messaging "
            "services in Python. Three years of experience with APIs are required. Fluent "
            "English is required."
        ),
    ),
    (
        "oakhaven-open-data",
        "Backend Developer, Open Data",
        "Oakhaven Public Data",
        "Amsterdam, Netherlands (hybrid)",
        "search",
        0.3,
        ("EUR", 58000, 70000),
        (
            "Oakhaven Public Data publishes open data for Dutch municipalities. Our team of nine "
            "works from Amsterdam."
        ),
        (
            "You will maintain our Python APIs and import pipelines and help municipalities "
            "publish new datasets. Fluent English is required; Dutch is a plus."
        ),
    ),
)

COMPANIES = frozenset(
    {
        "Voltline Grid Analytics",
        "Carbon Ledger Foundation",
        "Tessellate Maps",
        "Lumacare Health",
        "Larchmont Bank",
        "Freightwise",
        "Quayside Payments",
        "Kelpie Labs",
        "Meridian Insurance Group",
        "Fernhill Mobility",
        "Cobalt Telecom",
        "Spreeland Energie GmbH",
        "Pixelwright Studio",
        "Northpeak Trading",
        "Saltmarsh Analytics",
        "Lindgren Climate Tech",
        *(job[2] for job in NEW_JOBS),
    }
)
