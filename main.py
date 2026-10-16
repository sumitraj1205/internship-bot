"""
Internship Alert Bot (runs once per GitHub Actions schedule).

Scans the official career boards of AI / data companies for Data Science,
AI and ML internships and sends new ones to your Telegram with an
"Apply Now" button.  It auto-detects which hiring platform each company uses
(Greenhouse, Lever, Ashby, Workable, Recruitee, SmartRecruiters)
plus Workday, Amazon and job-site APIs (Adzuna, Jooble, The Muse, Remotive, Jobicy, Arbeitnow, Remote OK).
"""
import hashlib
import html
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import httpx

# ======================= SETTINGS YOU CAN EDIT =======================

# One company per line:  "Display Name: slug1, slug2"
# The slug is the company's name inside its careers-page link, e.g.
#   jobs.lever.co/palantir  ->  palantir
# Give 2 guesses if you're unsure.  Companies not found are listed in the run
# log as "NOT FOUND" and are simply skipped.  To add a company, add a line.
COMPANIES = [
    # ---------- AI labs & model companies ----------
    "Anthropic: anthropic",
    "OpenAI: openai",
    "Google DeepMind: deepmind",
    "xAI: xai",
    "Mistral AI: mistral, mistralai",
    "Cohere: cohere",
    "Perplexity: perplexity, perplexityai",
    "Character.AI: character, characterai",
    "Hugging Face: huggingface",
    "Stability AI: stabilityai",
    "Runway: runwayml, runway",
    "ElevenLabs: elevenlabs",
    "Together AI: togetherai, together",
    "Anyscale: anyscale",
    "Modal: modal",
    "Replicate: replicate",
    "Weights & Biases: wandb",
    "Scale AI: scaleai, scale",
    "Snorkel AI: snorkelai",
    "Labelbox: labelbox",
    "Adept: adept",
    "Inflection AI: inflectionai",
    "Reka AI: rekaai",
    "Luma AI: lumaai",
    "Suno: suno",
    "Midjourney: midjourney",
    "Black Forest Labs: blackforestlabs",
    "Sakana AI: sakanaai",
    # ---------- AI developer tools & vector DBs ----------
    "Pinecone: pinecone",
    "Weaviate: weaviate",
    "Qdrant: qdrant",
    "Chroma: trychroma, chroma",
    "LangChain: langchain",
    "LlamaIndex: llamaindex",
    "Cursor (Anysphere): anysphere",
    "Cognition: cognition",
    "Replit: replit",
    "Sourcegraph: sourcegraph",
    "Vercel: vercel",
    "Codeium / Windsurf: codeium",
    "Tabnine: tabnine",
    "Poolside: poolside",
    "Magic: magic",
    # ---------- Applied AI products ----------
    "Harvey: harvey",
    "Glean: gleanwork, glean",
    "Writer: writer",
    "Jasper: jasper",
    "Abridge: abridge",
    "Hippocratic AI: hippocraticai",
    "Sierra: sierra",
    "Decagon: decagon",
    "Cresta: cresta",
    "Moveworks: moveworks",
    "Gong: gong",
    "Grammarly: grammarly",
    "Synthesia: synthesia",
    "Descript: descript",
    "Tome: tome",
    "Typeface: typeface",
    "Hebbia: hebbia",
    "Rogo: rogo",
    "Ironclad: ironclad",
    "Clay: clay",
    # ---------- Data & ML infrastructure ----------
    "Databricks: databricks",
    "Snowflake: snowflake",
    "DataRobot: datarobot",
    "H2O.ai: h2oai",
    "Dataiku: dataiku",
    "Domino Data Lab: dominodatalab",
    "Hex: hex",
    "Fivetran: fivetran",
    "dbt Labs: dbtlabsinc, dbtlabs",
    "Airbyte: airbyte",
    "Datadog: datadog",
    "Elastic: elastic",
    "MongoDB: mongodb",
    "Confluent: confluent",
    "Astronomer: astronomer",
    "Prefect: prefect",
    "Dagster: dagsterlabs",
    "Comet: cometml, comet",
    "Arize AI: arizeai",
    "Fiddler AI: fiddlerlabs",
    "Cerebras: cerebrassystems, cerebras",
    "SambaNova: sambanova",
    "Groq: groq",
    "Lambda: lambda, lambdalabs",
    "CoreWeave: coreweave",
    "Crusoe: crusoe",
    "DataStax: datastax",
    "ThoughtSpot: thoughtspot",
    "Deepgram: deepgram",
    "AssemblyAI: assemblyai",
    "Zilliz: zilliz",
    # ---------- Deep-tech / robotics / health AI ----------
    "Palantir: palantir",
    "Anduril: anduril",
    "Shield AI: shieldai",
    "Applied Intuition: appliedintuition",
    "Nuro: nuro",
    "Waabi: waabi",
    "Samsara: samsara",
    "Verkada: verkada",
    "Tempus: tempus",
    "Insitro: insitro",
    "Recursion: recursionpharma, recursion",
    "Benchling: benchling",
    "Figure AI: figureai, figure",
    "Skydio: skydio",
    # ---------- Big product companies (strong ML intern programs) ----------
    "Stripe: stripe",
    "Airbnb: airbnb",
    "Cloudflare: cloudflare",
    "Figma: figma",
    "Coinbase: coinbase",
    "Pinterest: pinterest",
    "Twilio: twilio",
    "Reddit: reddit",
    "Discord: discord",
    "Duolingo: duolingo",
    "Instacart: instacart",
    "Lyft: lyft",
    "Robinhood: robinhood",
    "Affirm: affirm",
    "Brex: brex",
    "Ramp: ramp",
    "Plaid: plaid",
    "Notion: notion",
    "Airtable: airtable",
    "Dropbox: dropbox",
    "Asana: asana",
    "GitLab: gitlab",
    "Okta: okta",
    "Gusto: gusto",
    "Carta: carta",
    "Webflow: webflow",
    "Spotify: spotify",
    # ---------- India: AI & analytics companies ----------
    "Sarvam AI: sarvam, sarvamai",
    "Krutrim: krutrim",
    "Observe.AI: observeai, observe",
    "Uniphore: uniphore",
    "Yellow.ai: yellowai, yellow",
    "Gupshup: gupshup",
    "Haptik: haptik",
    "Mad Street Den: madstreetden",
    "Wadhwani AI: wadhwaniai",
    "Quantiphi: quantiphi",
    "Tredence: tredence",
    "Sigmoid: sigmoid",
    "Tiger Analytics: tigeranalytics",
    "LatentView: latentview",
    "Gramener: gramener",
    "Atlan: atlan",
    "Hasura: hasura",
    # ---------- India: product startups & unicorns ----------
    "Razorpay: razorpaysoftwareprivatelimited, razorpay",
    "Groww: groww",
    "CRED: cred",
    "Meesho: meesho",
    "PhonePe: phonepe",
    "Swiggy: swiggy",
    "Zomato: zomato",
    "Zepto: zepto, zeptonow",
    "Paytm: paytm",
    "Dream Sports: dreamsports, dream11",
    "Freshworks: freshworks",
    "Postman: postman",
    "BrowserStack: browserstack",
    "Chargebee: chargebee",
    "Druva: druva",
    "Sprinklr: sprinklr",
    "CleverTap: clevertap",
    "MoEngage: moengage",
    "Rapido: rapido",
    "Urban Company: urbancompany",
    "Juspay: juspay",
    "Cashfree: cashfree",
    "Navi: navi",
    "InMobi: inmobi",
    "ShareChat: sharechat",
    "PhysicsWallah: physicswallah",
    "upGrad: upgrad",
    "Unacademy: unacademy",
    "Zeta: zeta",
    "Slice: sliceit, slice",
    # ---------- MORE AI / ML startups (global) ----------
    "Surge AI: surgeai",
    "Turing: turing",
    "Invisible Technologies: invisibletech, invisible",
    "Mercor: mercor",
    "Encord: encord",
    "V7 Labs: v7labs, v7",
    "Roboflow: roboflow",
    "Clarifai: clarifai",
    "Cleanlab: cleanlab",
    "SuperAnnotate: superannotate",
    "Dataloop: dataloop",
    "Humanloop: humanloop",
    "Lightning AI: lightningai, lightning",
    "Gretel: gretel, gretelai",
    "Tonic.ai: tonicai, tonic",
    "Cerebrium: cerebrium",
    "Baseten: baseten",
    "Fireworks AI: fireworksai, fireworks",
    "OctoAI: octoml, octoai",
    "Lamini: lamini",
    "Unstructured: unstructured",
    "Vellum: vellum",
    "Voyage AI: voyageai",
    "Contextual AI: contextualai",
    "Imbue: imbue",
    "Essential AI: essentialai",
    "Liquid AI: liquidai",
    "AI21 Labs: ai21, ai21labs",
    "Aleph Alpha: alephalpha",
    "DeepL: deepl",
    "Photoroom: photoroom",
    "H Company: hcompany",
    "Wayve: wayve",
    "Helsing: helsing",
    "Cradle: cradle",
    "Isomorphic Labs: isomorphiclabs",
    "PolyAI: polyai",
    "Speechmatics: speechmatics",
    "Graphcore: graphcore",
    "Faculty: faculty, facultyai",
    "Peak AI: peakai, peak",
    "Tractable: tractable",
    "Onfido: onfido",
    "Darktrace: darktrace",
    "Featurespace: featurespace",
    "Quantexa: quantexa",
    "Physical Intelligence: physicalintelligence, pi",
    "Skild AI: skildai, skild",
    "Covariant: covariant",
    "Gecko Robotics: geckorobotics",
    "Aurora Innovation: aurorainnovation, aurora",
    "Planet Labs: planet, planetlabs",
    "Flock Safety: flocksafety",
    "Motive: gomotive, motive",
    "Rivian: rivian",
    "Joby Aviation: jobyaviation, joby",
    "C3.ai: c3iot, c3ai",
    "Veritone: veritone",
    "SoundHound AI: soundhound",
    "Granola: granola",
    "Lovable: lovable",
    "Bolt.new (StackBlitz): stackblitz",
    "Pika: pika, pikalabs",
    "Genmo: genmo",
    "Ideogram: ideogram",
    "Krea: krea",
    "Leonardo.Ai: leonardoai, leonardo",
    "Canva: canva",
    "Hume AI: hume, humeai",
    "Cartesia: cartesia",
    "Retell AI: retellai",
    "Vapi: vapi",
    "Bland AI: blandai",
    "Parloa: parloa",
    "Ada: ada, adasupport",
    "Forethought: forethought",
    "Cohere Health: coherehealth",
    # ---------- Dev tools / data / cloud (ML-heavy teams) ----------
    "Rippling: rippling",
    "Linear: linear",
    "Retool: retool",
    "Supabase: supabase",
    "Neon: neon",
    "PlanetScale: planetscale",
    "Temporal: temporal",
    "Vanta: vanta",
    "Drata: drata",
    "New Relic: newrelic",
    "PagerDuty: pagerduty",
    "Sentry: sentry",
    "LaunchDarkly: launchdarkly",
    "HashiCorp: hashicorp",
    "Cockroach Labs: cockroachlabs",
    "Redis: redis",
    "Neo4j: neo4j",
    "Couchbase: couchbase",
    "SingleStore: singlestore",
    "Starburst: starburst",
    "Dremio: dremio",
    "Imply: imply",
    "ClickHouse: clickhouse",
    "Materialize: materialize",
    "Amplitude: amplitude",
    "Mixpanel: mixpanel",
    "PostHog: posthog",
    "Statsig: statsig",
    "Braze: braze",
    "Iterable: iterable",
    "Klaviyo: klaviyo",
    "HubSpot: hubspot",
    "Intercom: intercom",
    "Gainsight: gainsight",
    "Outreach: outreach",
    "Clari: clari",
    "6sense: 6sense",
    "ZoomInfo: zoominfo",
    "Snyk: snyk",
    "Cohesity: cohesity",
    "Rubrik: rubrik",
    "Nutanix: nutanix",
    "Pure Storage: purestorage",
    "Splunk: splunk",
    "Sumo Logic: sumologic",
    "Dynatrace: dynatrace",
    "Grafana Labs: grafanalabs",
    "Tailscale: tailscale",
    "Fastly: fastly",
    "DigitalOcean: digitalocean",
    "Fly.io: flyio",
    "Render: render",
    "Netlify: netlify",
    "Algolia: algolia",
    "Contentful: contentful",
    "Sanity: sanity",
    "Mapbox: mapbox",
    "Esri: esri",
    # ---------- Consumer / marketplace / fintech with big ML teams ----------
    "DoorDash: doordash",
    "Flexport: flexport",
    "Faire: faire",
    "Roblox: roblox",
    "Squarespace: squarespace",
    "Etsy: etsy",
    "Wayfair: wayfair",
    "Peloton: peloton",
    "Strava: strava",
    "Whoop: whoop",
    "Oura: oura",
    "Calm: calm",
    "Headspace: headspace",
    "Coursera: coursera",
    "Udemy: udemy",
    "Khan Academy: khanacademy",
    "Quizlet: quizlet",
    "Scribd: scribd",
    "Medium: medium",
    "Substack: substack",
    "Patreon: patreon",
    "Chime: chime",
    "SoFi: sofi",
    "Upstart: upstart",
    "Mercury: mercury",
    "Navan: navan",
    "Deel: deel",
    "Zip: ziphq",
    "Addepar: addepar",
    "Betterment: betterment",
    "Wealthfront: wealthfront",
    "Marqeta: marqeta",
    "Toast: toast",
    "Nubank: nubank",
    "Wise: wise",
    "Monzo: monzo",
    "Revolut: revolut",
    "Klarna: klarna",
    "Checkout.com: checkoutcom, checkout",
    "Airwallex: airwallex",
    "Zocdoc: zocdoc",
    "Oscar Health: oscar, oscarhealth",
    "Color Health: color",
    "Nabla: nabla",
    "Ambience Healthcare: ambiencehealthcare, ambience",
    "Suki: suki",
    "Viz.ai: vizai",
    "Aidoc: aidoc",
    "PathAI: pathai",
    "Owkin: owkin",
    "Atomwise: atomwise",
    "Exscientia: exscientia",
    "BenevolentAI: benevolentai",
    "Freenome: freenome",
    "Genesis Therapeutics: genesistherapeutics",
    # ---------- INDIA: AI, analytics, deep-tech ----------
    "Fractal Analytics: fractal, fractalanalytics",
    "Mu Sigma: musigma",
    "MathCo: mathco, themathcompany",
    "Course5 Intelligence: course5, course5intelligence",
    "Affine: affine",
    "BridgeI2I: bridgei2i",
    "Subex: subex",
    "Netradyne: netradyne",
    "Ather Energy: atherenergy, ather",
    "Ola Electric: olaelectric",
    "Skit.ai: skit, skitai",
    "Verloop.io: verloop",
    "Kore.ai: koreai, kore",
    "Engati: engati",
    "Gnani.ai: gnani, gnaniai",
    "Convin: convin",
    "Leena AI: leenaai, leena",
    "CoRover: corover",
    "Shaip: shaip",
    "Josh Talks: joshtalks",
    "Pocket FM: pocketfm",
    "Kuku FM: kukufm",
    "Innovaccer: innovaccer",
    "Qure.ai: qureai, qure",
    "Niramai: niramai",
    "Tricog: tricog",
    "SigTuple: sigtuple",
    "Wingify: wingify",
    "Whatfix: whatfix",
    "Mindtickle: mindtickle",
    "Capillary Technologies: capillary, capillarytech",
    "Netcore Cloud: netcore",
    "Zenoti: zenoti",
    "Darwinbox: darwinbox",
    "Keka: keka",
    "Icertis: icertis",
    "Amagi: amagi",
    "Exotel: exotel",
    "Ozonetel: ozonetel",
    "LeadSquared: leadsquared",
    "Perfios: perfios",
    "Signzy: signzy",
    "IDfy: idfy",
    "HyperVerge: hyperverge",
    "Bureau: bureau",
    "Setu: setu",
    "Sprinto: sprinto",
    "Zluri: zluri",
    "Rocketlane: rocketlane",
    "Glance: glance",
    "Dailyhunt: dailyhunt",
    # ---------- INDIA: fintech ----------
    "Pine Labs: pinelabs",
    "BharatPe: bharatpe",
    "Lendingkart: lendingkart",
    "KreditBee: kreditbee",
    "Jupiter Money: jupiter, jupitermoney",
    "Fi Money (Epifi): epifi",
    "Khatabook: khatabook",
    "OkCredit: okcredit",
    "Moneyview: moneyview",
    "Dhan: dhan",
    "Upstox: upstox",
    "Zerodha: zerodha",
    "Smallcase: smallcase",
    "Scripbox: scripbox",
    "INDmoney: indmoney",
    "PB Fintech (Policybazaar): pbfintech, policybazaar",
    "Acko: acko",
    "Digit Insurance: godigit, digit",
    "MobiKwik: mobikwik",
    "Freecharge: freecharge",
    "Open Financial: open, openfinancial",
    "Decentro: decentro",
    # ---------- INDIA: consumer / commerce / mobility / games ----------
    "Cars24: cars24",
    "Spinny: spinny",
    "CarDekho: cardekho",
    "Nykaa: nykaa",
    "Lenskart: lenskart",
    "Honasa (Mamaearth): honasa",
    "boAt: boatlifestyle, boat",
    "Licious: licious",
    "FreshToHome: freshtohome",
    "Country Delight: countrydelight",
    "Blinkit: blinkit",
    "Dunzo: dunzo",
    "Shadowfax: shadowfax",
    "Delhivery: delhivery",
    "Ecom Express: ecomexpress",
    "Porter: porter",
    "BlackBuck: blackbuck",
    "Udaan: udaan",
    "Mensa Brands: mensabrands",
    "OYO: oyo",
    "MakeMyTrip: makemytrip",
    "ixigo: ixigo",
    "Cleartrip: cleartrip",
    "RedBus: redbus",
    "MPL (Mobile Premier League): mpl",
    "Games24x7: games24x7",
    "Nazara: nazara",
    "Zupee: zupee",
    "WinZO: winzo",
    "Loco: loco",
    "PharmEasy: pharmeasy",
    "Practo: practo",
    "HealthifyMe: healthifyme",
    "Eka Care: ekacare",
    "Cure.fit (Cult.fit): curefit, cultfit",
    # ---------- INDIA: edtech ----------
    "Vedantu: vedantu",
    "BYJU'S: byjus",
    "Eruditus: eruditus",
    "Scaler: scaler",
    "Newton School: newtonschool",
    "Masai School: masaischool",
    "Simplilearn: simplilearn",
    "Coding Ninjas: codingninjas",
    "Great Learning: greatlearning",
    "Cuemath: cuemath",
    "Testbook: testbook",
    "Internshala: internshala",
    "Apna: apna",
    "Unstop: unstop",
]

# The job title must contain one INTERN word AND one ROLE word.
INTERN_KEYWORDS = ["intern", "interns", "internship", "trainee", "apprentice", "co-op", "coop"]
ROLE_KEYWORDS = [
    "data science", "data scientist", "machine learning", "ml", "ai",
    "artificial intelligence", "llm", "nlp", "computer vision", "deep learning",
    "generative", "genai", "applied scientist", "research engineer",
    "research scientist", "data analyst", "data engineer",
]

# Only jobs whose location contains one of these words are sent.
# Make it an empty list [] to receive jobs from ALL locations worldwide.
LOCATION_FILTER = [
    "india", "remote", "anywhere", "bengaluru", "bangalore", "hyderabad", "pune",
    "mumbai", "delhi", "gurgaon", "gurugram", "noida", "chennai", "kolkata", "worldwide",
]

# ---------- BIG COMPANIES THAT USE "WORKDAY" CAREER SITES ----------
# Format:  "Name | host | site"   (copy host and site from the company's careers link:
#   https://HOST.myworkdayjobs.com/en-US/SITE/... )
# Wrong entries are just skipped and shown as "Skipping" in the run log.
WORKDAY = [
    "NVIDIA | nvidia.wd5 | NVIDIAExternalCareerSite",
    "Adobe | adobe.wd5 | external_experienced",
    "Salesforce | salesforce.wd12 | External_Career_Site",
    "Intel | intel.wd1 | External",
    "Dell Technologies | dell.wd1 | External",
    "Walmart Global Tech | walmart.wd5 | WalmartExternal",
    "Mastercard | mastercard.wd1 | CorporateCareers",
    "Capital One | capitalone.wd12 | Capital_One",
    "Qualcomm | qualcomm.wd5 | External",
    "Micron | micron.wd1 | External",
    "Wells Fargo | wf.wd1 | WellsFargoJobs",
    "Citi | citi.wd5 | 2",
    "PwC | pwc.wd3 | Global_Experienced_Careers",
    "HP Inc | hp.wd5 | ExternalCareerSite",
    "HPE | hpe.wd5 | Jobsathpe",
    "Zoom | zoom.wd5 | Zoom",
    "Workday | workday.wd5 | Workday",
    "Thomson Reuters | thomsonreuters.wd5 | External_Career_Site",
    "S&P Global | spgi.wd5 | SPGI_Careers",
    "Moody's | moodys.wd5 | MoodysCareers",
    "BlackRock | blackrock.wd1 | BlackRock_Professional",
    "State Street | statestreet.wd1 | Global",
    "Broadcom | broadcom.wd1 | External_Career",
    "Autodesk | autodesk.wd1 | uni",
    "Target | target.wd5 | targetcareers",
    "Pfizer | pfizer.wd1 | PfizerCareers",
    "Snap | snap.wd1 | snap",
]

# ---------- BIG NAMES VIA ADZUNA (TCS, Infosys, Accenture, Deloitte, Goldman...) ----------
# These companies don't publish a public job feed, so we search India listings on
# Adzuna (free API key needed, see guide) and keep ONLY the companies named here.
BIG_COMPANIES = [
    "Tata Consultancy", "TCS", "Infosys", "Wipro", "HCL", "HCLTech", "Tech Mahindra",
    "Cognizant", "Capgemini", "Accenture", "Deloitte", "EY", "Ernst & Young", "KPMG",
    "PwC", "PricewaterhouseCoopers", "Goldman Sachs", "JPMorgan", "J.P. Morgan",
    "Morgan Stanley", "Citi", "Citigroup", "Barclays", "HSBC", "Standard Chartered",
    "Deutsche Bank", "UBS", "Nomura", "American Express", "Mastercard", "Visa Inc",
    "Bosch", "Siemens", "IBM", "Oracle", "SAP", "Microsoft", "Google", "Amazon",
    "Intel", "Cisco", "Dell", "Adobe", "Walmart", "Flipkart", "Samsung", "LTIMindtree",
    "Mphasis", "Hexaware", "Persistent Systems", "Zensar", "Genpact", "ZS Associates",
    "Mu Sigma", "Fractal", "Tiger Analytics", "BCG", "Boston Consulting", "McKinsey",
    "Bain", "BlackRock", "Wells Fargo", "Bank of America", "S&P Global",
    "Thomson Reuters", "Nvidia", "Qualcomm", "Salesforce", "ServiceNow", "Honeywell",
    # more big tech / FAANG-style names
    "Meta", "Meta Platforms", "Facebook", "Apple", "Netflix", "Uber", "LinkedIn", "Tesla",
    "PayPal", "Atlassian", "VMware", "Broadcom", "AMD", "Texas Instruments", "Micron",
    "Synopsys", "Cadence", "Autodesk", "Workday", "Zoom", "Twilio", "Expedia", "Booking",
    "Ericsson", "Nokia", "Philips", "GE", "General Electric", "Schneider Electric", "ABB",
    # more Indian IT / consulting / banks / conglomerates
    "Larsen & Toubro", "L&T", "LTI", "Tata Elxsi", "Tata Digital", "Tata 1mg", "Reliance",
    "Jio", "Airtel", "Bharti", "HDFC", "ICICI", "Axis Bank", "Kotak", "Bajaj", "Mahindra",
    "Coforge", "Nagarro", "EPAM", "Thoughtworks", "Publicis Sapient", "Sapient", "Virtusa",
    "Birlasoft", "Cyient", "Sonata Software", "Happiest Minds", "Mastek", "Kellton",
    "Mckinsey", "Kearney", "Oliver Wyman", "Alvarez", "Grant Thornton", "BDO", "Protiviti",
    "Fidelity", "Vanguard", "Charles Schwab", "Northern Trust", "Franklin Templeton",
    "Nasdaq", "Moody's", "Moodys", "Fitch", "Morningstar", "MSCI", "Bloomberg",
]
ADZUNA_QUERIES = ["data science intern", "machine learning intern", "AI intern", "AI engineer intern",
                  "data analyst intern", "NLP intern"]
SLOW_SOURCES_EVERY_HOURS = 6   # job-site APIs (Adzuna, Jooble, Remotive...) run every 6 hours to respect their limits
JOOBLE_QUERIES = ["data science intern", "machine learning intern", "AI intern", "AI engineer intern", "data analyst intern"]
THE_MUSE_CATEGORIES = ["Data Science", "Data and Analytics", "Software Engineering"]

# ---------- RESEARCH INTERNSHIPS: IITs, NITs, IIITs, IISc, IISERs, Science Academies ----------
# The bot opens these official pages twice a day and alerts you when a NEW internship /
# summer-research / fellowship notice appears.  Add or remove lines freely.
WATCH_EVERY_HOURS = 12

# Dedicated program pages (we also alert on new announcement TEXT on these pages).
RESEARCH_PROGRAM_PAGES = [
    ("IIT Bombay Research Internship (IRCC)", "https://www.ircc.iitb.ac.in/IRCC-Webpage/IITBInternship/"),
    ("IIT Madras YRF", "https://yrf.iitm.ac.in/index.html"),
    ("IIT Madras Summer Fellowship", "https://ssp.iitm.ac.in/summer-fellowship-registration"),
    ("IIT Delhi Summer Research (SRF)", "https://academics.iitd.ac.in/srf/"),
    ("IIT Kanpur SURGE", "https://surge.iitk.ac.in/"),
    ("IIT Kanpur Internship Opportunities", "https://www.iitk.ac.in/doaa/opportunities-for-internship"),
]

# Institute home pages (we alert on NEW links whose text mentions internship / summer research ...).
INSTITUTE_HOMEPAGES = [
    # IITs
    ("IIT Bombay", "https://www.iitb.ac.in/"), ("IIT Delhi", "https://home.iitd.ac.in/"),
    ("IIT Madras", "https://www.iitm.ac.in/"), ("IIT Kanpur", "https://www.iitk.ac.in/"),
    ("IIT Kharagpur", "https://www.iitkgp.ac.in/"), ("IIT Roorkee", "https://www.iitr.ac.in/"),
    ("IIT Guwahati", "https://www.iitg.ac.in/"), ("IIT Hyderabad", "https://www.iith.ac.in/"),
    ("IIT Gandhinagar", "https://iitgn.ac.in/"), ("IIT BHU", "https://www.iitbhu.ac.in/"),
    ("IIT (ISM) Dhanbad", "https://www.iitism.ac.in/"), ("IIT Indore", "https://www.iiti.ac.in/"),
    ("IIT Bhubaneswar", "https://www.iitbbs.ac.in/"), ("IIT Jodhpur", "https://iitj.ac.in/"),
    ("IIT Patna", "https://www.iitp.ac.in/"), ("IIT Ropar", "https://www.iitrpr.ac.in/"),
    ("IIT Mandi", "https://www.iitmandi.ac.in/"), ("IIT Tirupati", "https://www.iittp.ac.in/"),
    ("IIT Palakkad", "https://iitpkd.ac.in/"), ("IIT Goa", "https://www.iitgoa.ac.in/"),
    ("IIT Dharwad", "https://www.iitdh.ac.in/"), ("IIT Jammu", "https://www.iitjammu.ac.in/"),
    ("IIT Bhilai", "https://www.iitbhilai.ac.in/"),
    # NITs
    ("NIT Trichy", "https://www.nitt.edu/"), ("NIT Surathkal", "https://www.nitk.ac.in/"),
    ("NIT Warangal", "https://www.nitw.ac.in/"), ("NIT Rourkela", "https://www.nitrkl.ac.in/"),
    ("MNIT Jaipur", "https://www.mnit.ac.in/"), ("NIT Calicut", "https://nitc.ac.in/"),
    ("NIT Durgapur", "https://nitdgp.ac.in/"), ("NIT Jamshedpur", "https://www.nitjsr.ac.in/"),
    ("NIT Kurukshetra", "https://nitkkr.ac.in/"), ("NIT Srinagar", "https://nitsri.ac.in/"),
    ("MANIT Bhopal", "https://www.manit.ac.in/"), ("SVNIT Surat", "https://www.svnit.ac.in/"),
    ("NIT Raipur", "https://www.nitrr.ac.in/"), ("NIT Patna", "https://www.nitp.ac.in/"),
    ("NIT Silchar", "https://www.nits.ac.in/"), ("MNNIT Allahabad", "https://www.mnnit.ac.in/"),
    ("VNIT Nagpur", "https://vnit.ac.in/"), ("NIT Hamirpur", "https://nith.ac.in/"),
    ("NIT Goa", "https://www.nitgoa.ac.in/"),
    # IIITs
    ("IIIT Hyderabad", "https://www.iiit.ac.in/"), ("IIIT Delhi", "https://www.iiitd.ac.in/"),
    ("IIIT Bangalore", "https://www.iiitb.ac.in/"), ("IIIT Allahabad", "https://www.iiita.ac.in/"),
    ("IIITM Gwalior", "https://www.iiitm.ac.in/"), ("IIITDM Kancheepuram", "https://www.iiitdm.ac.in/"),
    ("IIIT Guwahati", "https://www.iiitg.ac.in/"), ("IIIT Kota", "https://iiitkota.ac.in/"),
    ("IIIT Lucknow", "https://iiitl.ac.in/"), ("IIIT Vadodara", "https://iiitvadodara.ac.in/"),
    ("IIIT Sri City", "https://www.iiits.ac.in/"), ("IIIT Pune", "https://www.iiitp.ac.in/"),
    ("IIIT Nagpur", "https://iiitn.ac.in/"), ("IIIT Naya Raipur", "https://www.iiitnr.ac.in/"),
    # Other research institutes and national programs
    ("IISc Bangalore", "https://iisc.ac.in/"), ("IISER Pune", "https://www.iiserpune.ac.in/"),
    ("IISER Bhopal", "https://www.iiserb.ac.in/"), ("IISER Kolkata", "https://www.iiserkol.ac.in/"),
    ("IISER Mohali", "https://www.iisermohali.ac.in/"), ("IISER Tirupati", "https://www.iisertirupati.ac.in/"),
    ("IISER Thiruvananthapuram", "https://www.iisertvm.ac.in/"), ("JNCASR", "https://www.jncasr.ac.in/"),
    ("TIFR", "https://www.tifr.res.in/"), ("ISI Kolkata", "https://www.isical.ac.in/"),
    ("Indian Academy of Sciences (SRFP)", "https://www.ias.ac.in/"),
    ("INSA (SRFP)", "https://insaindia.res.in/"), ("NASI (SRFP)", "https://www.nasi.org.in/"),
    ("DRDO", "https://www.drdo.gov.in/"), ("ISRO", "https://www.isro.gov.in/"),
]

# Words that make a link / sentence count as a research-internship notice.
RESEARCH_TOPIC_WORDS = [
    "intern", "interns", "internship", "internships", "summer research", "summer fellowship",
    "summer internship", "winter internship", "winter research", "research internship",
    "summer program", "summer programme", "summer school", "surge", "srip", "srfp",
    "visiting student", "non-degree student", "research fellowship", "undergraduate research",
]
RESEARCH_EXCLUDE_WORDS = [
    "phd", "ph.d", "post-doctoral", "postdoctoral", "postdoc", "faculty", "tender", "recruitment",
    "m.tech", "mba", "jrf", "project associate", "walk-in", "quotation", "empanelment",
]
RESEARCH_ACTION_WORDS = [
    "apply", "application", "applications", "open", "opens", "opened", "deadline", "last date",
    "call for", "invited", "invites", "invitation", "registration", "register", "extended", "announce",
    "announced", "notification", "schedule",
]

FIRST_RUN_LIMIT = 25   # first run: send at most this many, save the rest silently
MAX_PER_RUN = 30       # later runs: send at most this many; the rest follow next hour

# =====================================================================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
STATE_FILE = Path("seen.json")  # remembers which jobs were already sent


def _compile(words):
    return re.compile(r"(?<![a-z])(" + "|".join(re.escape(w) for w in words) + r")(?![a-z])", re.I)


INTERN_RE = _compile(INTERN_KEYWORDS)
ROLE_RE = _compile(ROLE_KEYWORDS)

# Location matching uses whole words, so "india" does NOT match "Indianapolis".
REMOTE_WORDS = {"remote", "anywhere", "worldwide"}
_PLACE_WORDS = [k for k in LOCATION_FILTER if k not in REMOTE_WORDS]
PLACE_RE = _compile(_PLACE_WORDS) if _PLACE_WORDS else None
WANTS_REMOTE = any(k in REMOTE_WORDS for k in LOCATION_FILTER)
REMOTE_RE = re.compile(r"remote|anywhere|worldwide|work from home", re.I)
# "Remote in USA", "Remote - EU" etc. are NOT open to you, so they are rejected.
REGION_ONLY_RE = re.compile(
    r"(?<![a-z])(usa|u\.s\.a?|us|united states|canada|uk|united kingdom|europe|eu|emea|americas|latam|"
    r"australia|germany|france|spain|netherlands|ireland|singapore|japan|brazil|mexico|poland|portugal)(?![a-z])",
    re.I,
)


def location_ok(loc):
    if not LOCATION_FILTER:
        return True
    if PLACE_RE and PLACE_RE.search(loc):
        return True
    return WANTS_REMOTE and bool(REMOTE_RE.search(loc)) and not REGION_ONLY_RE.search(loc)


# ------------------------------ fetchers ------------------------------
def fetch_greenhouse(client, slug, name):
    r = client.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    r.raise_for_status()
    return [
        {"uid": f"gh:{slug}:{j['id']}", "company": name, "title": j["title"],
         "location": (j.get("location") or {}).get("name", ""), "url": j["absolute_url"]}
        for j in r.json().get("jobs", [])
    ]


def fetch_lever(client, slug, name):
    r = client.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
    r.raise_for_status()
    return [
        {"uid": f"lv:{slug}:{j['id']}", "company": name, "title": j["text"],
         "location": (j.get("categories") or {}).get("location") or "", "url": j["hostedUrl"]}
        for j in r.json()
    ]


def fetch_ashby(client, slug, name):
    r = client.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    r.raise_for_status()
    return [
        {"uid": f"ab:{slug}:{j['id']}", "company": name, "title": j["title"],
         "location": j.get("location") or "", "url": j.get("jobUrl") or j.get("applyUrl") or ""}
        for j in r.json().get("jobs", [])
        if j.get("isListed", True)
    ]


def fetch_workable(client, slug, name):
    r = client.get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}", params={"details": "true"})
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        url = j.get("url") or j.get("shortlink") or j.get("application_url") or ""
        loc = ", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x)
        out.append({"uid": f"wk:{slug}:{j.get('shortcode') or url}", "company": name,
                    "title": j.get("title", ""), "location": loc, "url": url})
    return out


def fetch_recruitee(client, slug, name):
    r = client.get(f"https://{slug}.recruitee.com/api/offers/")
    r.raise_for_status()
    out = []
    for j in r.json().get("offers", []):
        loc = j.get("location") or ", ".join(x for x in (j.get("city"), j.get("country")) if x)
        out.append({"uid": f"rc:{slug}:{j['id']}", "company": name, "title": j.get("title", ""),
                    "location": loc, "url": j.get("careers_url") or ""})
    return out


def fetch_smartrecruiters(client, slug, name):
    r = client.get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
                   params={"limit": 100, "q": "intern"})
    r.raise_for_status()
    out = []
    for j in r.json().get("content", []):
        loc = j.get("location") or {}
        place = ", ".join(x for x in (loc.get("city"), loc.get("country")) if x)
        if loc.get("remote"):
            place = (place + ", Remote").strip(", ")
        out.append({"uid": f"sr:{slug}:{j['id']}", "company": name, "title": j.get("name", ""),
                    "location": place, "url": f"https://jobs.smartrecruiters.com/{slug}/{j['id']}"})
    return out


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workable": fetch_workable,
    "recruitee": fetch_recruitee,
    "smartrecruiters": fetch_smartrecruiters,
}


def parse_companies():
    out = []
    for line in COMPANIES:
        name, _, slugs = line.partition(":")
        slug_list = [s.strip() for s in slugs.split(",") if s.strip()]
        if name.strip() and slug_list:
            out.append((name.strip(), slug_list))
    return out


RETRY_MISSING_DAYS = 7  # companies with no board found are re-checked once a week


def safe_fetch(client, company, boards, missing):
    """Find the company's job board (remembered after the first run) and return its openings."""
    name, slugs = company
    known = boards.get(name)
    if known:
        try:
            return FETCHERS[known["ats"]](client, known["slug"], name)
        except Exception:
            pass  # board may have moved or a network blip: try to rediscover below
    elif time.time() - missing.get(name, 0) < RETRY_MISSING_DAYS * 86400:
        return []
    for slug in slugs:
        for ats, fn in FETCHERS.items():
            try:
                jobs = fn(client, slug, name)
            except Exception:
                continue
            if jobs:
                boards[name] = {"ats": ats, "slug": slug}
                missing.pop(name, None)
                print(f"FOUND      {name}: {ats}/{slug} ({len(jobs)} openings)")
                return jobs
    if not known:
        missing[name] = time.time()
        print(f"NOT FOUND  {name}: no public job board found for {slugs}")
    return []


def load_state():
    if not STATE_FILE.exists():
        return None
    data = json.loads(STATE_FILE.read_text())
    if isinstance(data, list):  # older format
        return {"seen": data, "boards": {}, "missing": {}, "watch_ready": False}
    return {"seen": data.get("seen", []), "boards": data.get("boards", {}), "missing": data.get("missing", {}),
            "watch_ready": data.get("watch_ready", False)}


def save_state(seen, boards, missing, watch_ready=False):
    STATE_FILE.write_text(json.dumps({"seen": sorted(seen), "boards": boards, "missing": missing,
                                      "watch_ready": watch_ready}, indent=0))



# ------------------- big-company sources -------------------
WORKDAY_SEARCHES = ["machine learning intern", "data science intern", "AI intern"]


def parse_workday():
    out = []
    for line in WORKDAY:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 3 and all(parts):
            out.append(tuple(parts))
    return out


def fetch_workday(client, name, host, site):
    tenant = host.split(".")[0]
    base = f"https://{host}.myworkdayjobs.com"
    api = f"{base}/wday/cxs/{tenant}/{site}/jobs"
    out = {}
    for text in WORKDAY_SEARCHES:
        for offset in (0, 20):
            r = client.post(api, json={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": text})
            r.raise_for_status()
            data = r.json()
            posts = data.get("jobPostings", [])
            for j in posts:
                path = j.get("externalPath", "")
                uid = f"wd:{tenant}:{path}"
                out[uid] = {"uid": uid, "company": name, "title": j.get("title", ""),
                            "location": j.get("locationsText", ""), "url": f"{base}/en-US/{site}{path}"}
            if len(posts) < 20 or offset + 20 >= data.get("total", 0):
                break
    return list(out.values())


def safe_workday(client, entry):
    name, host, site = entry
    try:
        return fetch_workday(client, name, host, site)
    except Exception as e:
        print(f"Skipping {name} (workday {host}/{site}): {e}")
        return []


def fetch_amazon(client):
    out = {}
    for q in ["machine learning intern", "data scientist intern", "applied scientist intern", "AI engineer intern"]:
        for loc in ("India", ""):
            r = client.get("https://www.amazon.jobs/en/search.json",
                           params={"base_query": q, "loc_query": loc, "result_limit": 100, "sort": "recent"})
            r.raise_for_status()
            for j in r.json().get("jobs", []):
                path = j.get("job_path", "")
                uid = f"amz:{j.get('id_icims') or path}"
                out[uid] = {"uid": uid, "company": "Amazon", "title": j.get("title", ""),
                            "location": j.get("normalized_location") or j.get("location") or "",
                            "url": "https://www.amazon.jobs" + path}
    return list(out.values())


BIG_RE = _compile(BIG_COMPANIES) if BIG_COMPANIES else None


def fetch_adzuna(client):
    app_id, app_key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        print("Adzuna skipped: no ADZUNA_APP_ID / ADZUNA_APP_KEY secrets set.")
        return []
    out = {}
    for q in ADZUNA_QUERIES:
        r = client.get("https://api.adzuna.com/v1/api/jobs/in/search/1",
                       params={"app_id": app_id, "app_key": app_key, "what": q, "results_per_page": 50,
                               "sort_by": "date", "max_days_old": 14})
        r.raise_for_status()
        for j in r.json().get("results", []):
            company = (j.get("company") or {}).get("display_name", "")
            if BIG_RE and not BIG_RE.search(company):
                continue
            uid = f"az:{j.get('id')}"
            loc = (j.get("location") or {}).get("display_name", "")
            out[uid] = {"uid": uid, "company": company, "title": j.get("title", ""),
                        "location": f"{loc}, India".strip(", "), "url": j.get("redirect_url", ""),
                        "source": "Adzuna"}
    return list(out.values())


# ------------------- more job sites (free APIs) -------------------
def _job(uid, company, title, location, url, source):
    return {"uid": uid, "company": company or "Unknown company", "title": title or "",
            "location": location or "", "url": url or "", "source": source}


def fetch_jooble(client):
    key = os.getenv("JOOBLE_API_KEY")
    if not key:
        print("Jooble skipped: no JOOBLE_API_KEY secret set.")
        return []
    out = {}
    for q in JOOBLE_QUERIES:
        r = client.post(f"https://jooble.org/api/{key}", json={"keywords": q, "location": "India", "page": 1})
        r.raise_for_status()
        for j in r.json().get("jobs", []):
            loc = j.get("location") or ""
            uid = f"jb:{j.get('id') or j.get('link')}"
            out[uid] = _job(uid, j.get("company"), j.get("title"), f"{loc}, India".strip(", "), j.get("link"), "Jooble")
    return list(out.values())


def fetch_muse(client):
    out = {}
    for page in range(3):
        r = client.get("https://www.themuse.com/api/public/jobs",
                       params={"level": "Internship", "category": THE_MUSE_CATEGORIES, "page": page})
        r.raise_for_status()
        data = r.json()
        for j in data.get("results", []):
            locs = ", ".join(l.get("name", "") for l in j.get("locations", [])) or "Flexible / Remote"
            uid = f"mu:{j.get('id')}"
            out[uid] = _job(uid, (j.get("company") or {}).get("name"), j.get("name"), locs,
                            (j.get("refs") or {}).get("landing_page"), "The Muse")
        if page + 1 >= data.get("page_count", 0):
            break
    return list(out.values())


def fetch_remotive(client):
    r = client.get("https://remotive.com/api/remote-jobs", params={"search": "intern", "limit": 100})
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        out.append(_job(f"rm:{j.get('id')}", j.get("company_name"), j.get("title"),
                        j.get("candidate_required_location") or "Remote", j.get("url"), "Remotive"))
    return out


def fetch_jobicy(client):
    r = client.get("https://jobicy.com/api/v2/remote-jobs", params={"count": 100, "tag": "intern"})
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        out.append(_job(f"jc:{j.get('id')}", j.get("companyName") or j.get("company"),
                        j.get("jobTitle") or j.get("title"), j.get("jobGeo") or "Remote", j.get("url"), "Jobicy"))
    return out


def fetch_arbeitnow(client):
    out = {}
    for page in (1, 2):
        r = client.get("https://www.arbeitnow.com/api/job-board-api", params={"page": page})
        r.raise_for_status()
        for j in r.json().get("data", []):
            loc = j.get("location") or ""
            if j.get("remote"):
                loc = f"{loc}, Remote".strip(", ")
            uid = f"an:{j.get('slug')}"
            out[uid] = _job(uid, j.get("company_name"), j.get("title"), loc, j.get("url"), "Arbeitnow")
    return list(out.values())


def fetch_remoteok(client):
    r = client.get("https://remoteok.com/api")
    r.raise_for_status()
    out = []
    for j in r.json():
        if not isinstance(j, dict) or "position" not in j:
            continue  # first element is a legal notice
        out.append(_job(f"ro:{j.get('id')}", j.get("company"), j.get("position"),
                        j.get("location") or "Remote", j.get("url"), "Remote OK"))
    return out


SLOW_SOURCES = [
    ("Adzuna (big companies)", fetch_adzuna),
    ("Jooble", fetch_jooble),
    ("The Muse", fetch_muse),
    ("Remotive", fetch_remotive),
    ("Jobicy", fetch_jobicy),
    ("Arbeitnow", fetch_arbeitnow),
    ("Remote OK", fetch_remoteok),
]


# ------------------- research internship pages (IIT / NIT / IIIT ...) -------------------
RESEARCH_TOPIC_RE = _compile(RESEARCH_TOPIC_WORDS)
RESEARCH_EXCLUDE_RE = _compile(RESEARCH_EXCLUDE_WORDS)
RESEARCH_ACTION_RE = _compile(RESEARCH_ACTION_WORDS)
CURRENT_CALL_RE = re.compile(r"2027|2026\s*[-\u2013/]\s*(20)?27|2027\s*[-\u2013/]\s*(20)?28")
_BLOCK_TAGS = {"p", "div", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "section",
               "article", "br", "ul", "ol", "table", "header", "footer", "nav", "marquee"}


class _PageParser(HTMLParser):
    """Collects links and readable text lines from an HTML page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.lines = [], []
        self._href = self._title = None
        self._atext, self._buf, self._skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        if tag == "a":
            d = dict(attrs)
            self._href, self._title, self._atext = d.get("href"), d.get("title"), []
        if tag in _BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = max(0, self._skip - 1)
        if tag == "a" and self._href is not None:
            text = " ".join("".join(self._atext).split()) or (self._title or "")
            self.links.append((self._href, text.strip()))
            self._href = None
        if tag in _BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        if self._skip:
            return
        self._buf.append(data)
        if self._href is not None:
            self._atext.append(data)

    def _flush(self):
        text = " ".join("".join(self._buf).split())
        self._buf = []
        if 20 <= len(text) <= 300:
            self.lines.append(text)


def _hash(*parts):
    return hashlib.md5("|".join(parts).encode("utf-8", "ignore")).hexdigest()[:16]


def _research_job(uid, org, title, url):
    return {"uid": uid, "company": org, "title": title[:200], "location": "India - research internship",
            "url": url, "source": "Official institute page", "research": True}


def scan_research_page(client, org, url, program):
    r = client.get(url)
    r.raise_for_status()
    page = _PageParser()
    page.feed(r.text)
    page.close()
    page._flush()
    link_texts = {t for _, t in page.links}
    jobs, seen_hrefs = [], set()
    for href, text in page.links:
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full = urljoin(str(r.url), href.strip())
        blob = f"{text} {full}"
        if full in seen_hrefs or not RESEARCH_TOPIC_RE.search(blob) or RESEARCH_EXCLUDE_RE.search(blob):
            continue
        seen_hrefs.add(full)
        label = text if len(text) >= 6 else full.rsplit("/", 1)[-1].replace("-", " ").replace("_", " ")
        jobs.append(_research_job("rs:" + _hash(full), org, label, full))
    if program:  # also watch announcement sentences on dedicated program pages
        for line in page.lines:
            if line in link_texts:
                continue  # already covered as a link
            if (RESEARCH_TOPIC_RE.search(line) and RESEARCH_ACTION_RE.search(line)
                    and not RESEARCH_EXCLUDE_RE.search(line)):
                jobs.append(_research_job("rl:" + _hash(url, line), org, line, url))
    return jobs[:20]


def fetch_research(client):
    """Returns (jobs, pages_reached). Uses its own client: Indian institute sites often have broken SSL."""
    targets = [(n, u, True) for n, u in RESEARCH_PROGRAM_PAGES] + [(n, u, False) for n, u in INSTITUTE_HOMEPAGES]

    def one(t):
        org, url, program = t
        try:
            return scan_research_page(client, org, url, program), True
        except Exception as e:
            print(f"Skipping research page {org}: {str(e)[:90]}")
            return [], False

    with ThreadPoolExecutor(16) as pool:
        results = list(pool.map(one, targets))
    jobs = [j for r, _ in results for j in r]
    reached = sum(1 for _, ok in results if ok)
    print(f"Research pages: {reached} of {len(targets)} reachable, {len(jobs)} candidate notices")
    return jobs, reached


def safe_call(label, fn, *args):
    try:
        jobs = fn(*args)
        print(f"{label}: {len(jobs)} openings fetched")
        return jobs
    except Exception as e:
        print(f"Skipping {label}: {e}")
        return []


def matches(job):
    if not job["url"].startswith("http"):
        return False
    if not INTERN_RE.search(job["title"]) or not ROLE_RE.search(job["title"]):
        return False
    return location_ok(job["location"])


# ------------------------------ telegram ------------------------------
def send(client, text, apply_url=None, keyboard=None):
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if keyboard:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    elif apply_url:
        payload["reply_markup"] = {"inline_keyboard": [[{"text": "🚀 Apply Now", "url": apply_url}]]}
    for _ in range(3):
        r = client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload)
        if r.status_code == 429:  # Telegram says "slow down"
            time.sleep(r.json().get("parameters", {}).get("retry_after", 5) + 1)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"Telegram error {r.status_code}: {r.text}")
        return
    raise RuntimeError("Telegram rate limit, will retry on next run")


def job_message(job):
    icon = "🎓" if job.get("research") else "🆕"
    return (
        f"{icon} <b>{html.escape(job['title'])}</b>\n"
        f"🏢 {html.escape(job['company'])}\n"
        f"📍 {html.escape(job['location'] or 'Not specified')}"
        + (f"\n🔗 via {html.escape(job['source'])}" if job.get("source") else "")
    )


# -------------------------------- main --------------------------------
def main():
    if not BOT_TOKEN or not CHAT_ID:
        sys.exit("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID. Add them in GitHub -> Settings -> Secrets.")

    state = load_state()
    first_run = state is None
    state = state or {"seen": [], "boards": {}, "missing": {}, "watch_ready": False}
    watch_ready = state.get("watch_ready", False)
    seen, boards, missing = set(state["seen"]), state["boards"], state["missing"]
    manual = os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"
    companies = parse_companies()

    with httpx.Client(timeout=15, follow_redirects=True, headers={"User-Agent": "internship-alert-bot/1.0"}) as client:
        with ThreadPoolExecutor(16) as pool:
            batches = list(pool.map(lambda c: safe_fetch(client, c, boards, missing), companies))
            wd_batches = list(pool.map(lambda e: safe_workday(client, e), parse_workday()))
        extra = [j for b in wd_batches for j in b]
        extra += safe_call("Amazon", fetch_amazon, client)
        if manual or first_run or time.gmtime().tm_hour % SLOW_SOURCES_EVERY_HOURS == 0:
            for label, fn in SLOW_SOURCES:
                extra += safe_call(label, fn, client)
        print(f"job boards known: {len(boards)} of {len(companies)} companies")
        everything = {j["uid"]: j for j in [x for b in batches for x in b] + extra}
        found = [j for j in everything.values() if matches(j)]

        # Research internships at IITs / NITs / IIITs (checked twice a day)
        intro_buttons = []
        if manual or first_run or not watch_ready or time.gmtime().tm_hour % WATCH_EVERY_HOURS == 0:
            try:
                with httpx.Client(timeout=20, follow_redirects=True, verify=False,
                                  headers={"User-Agent": "Mozilla/5.0 (compatible; internship-alert-bot/1.0)"}) as rclient:
                    research, reached = fetch_research(rclient)
            except Exception as e:
                print(f"Skipping research pages: {e}")
                research, reached = [], 0
            if reached and not watch_ready:
                # First time: remember the old notices silently, but still send ones about the 2027 cycle.
                for j in research:
                    if not CURRENT_CALL_RE.search(f"{j['title']} {j['url']}"):
                        seen.add(j["uid"])
                watch_ready = True
                intro_buttons = [[{"text": n[:40], "url": u}] for n, u in RESEARCH_PROGRAM_PAGES]
            found += [j for j in research if j["uid"] not in {x["uid"] for x in found}]
        new = [j for j in found if j["uid"] not in seen]
        limit = FIRST_RUN_LIMIT if first_run else MAX_PER_RUN
        to_send = new[:limit]
        silent = new[limit:] if first_run else []
        print(f"companies={len(companies)} matching={len(found)} new={len(new)} sending={len(to_send)}")

        if first_run:
            send(client, "✅ <b>Setup complete!</b> I check official company career pages every hour "
                         "and will message you new Data Science / AI internships here.")
        if intro_buttons:
            send(client, "🎓 <b>Research internships:</b> I now also watch IIT, NIT, IIIT, IISc and Science "
                         "Academies pages twice a day and will alert you to new internship / summer-research "
                         "notices. Main program pages:", keyboard=intro_buttons)
        try:
            for j in to_send:
                send(client, job_message(j), j["url"])
                seen.add(j["uid"])
                time.sleep(0.5)
            for j in silent:
                seen.add(j["uid"])
            if manual or first_run:
                left = len(new) - len(to_send) - len(silent)
                extra = f" ({left} more coming in the next hourly runs)" if left > 0 else ""
                send(client, f"ℹ️ Scan finished: {len(found)} matching openings right now, {len(new)} new{extra}.")
        finally:
            save_state(seen, boards, missing, watch_ready)


if __name__ == "__main__":
    main()
