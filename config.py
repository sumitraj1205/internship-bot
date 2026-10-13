"""Edit this file to change which companies and keywords the bot tracks."""

# (ATS type, board slug, display name)
# The slug is the part of the company's careers URL, e.g.
#   boards.greenhouse.io/<slug>   jobs.lever.co/<slug>   jobs.ashbyhq.com/<slug>
# If a slug is wrong the bot just logs a warning and skips it.
# Pulling directly from company career boards = only real, official listings.
COMPANIES = [
    # Greenhouse
    ("greenhouse", "anthropic", "Anthropic"),
    ("greenhouse", "databricks", "Databricks"),
    ("greenhouse", "scaleai", "Scale AI"),
    ("greenhouse", "stripe", "Stripe"),
    ("greenhouse", "airbnb", "Airbnb"),
    ("greenhouse", "cloudflare", "Cloudflare"),
    ("greenhouse", "datadog", "Datadog"),
    ("greenhouse", "mongodb", "MongoDB"),
    ("greenhouse", "gitlab", "GitLab"),
    ("greenhouse", "figma", "Figma"),
    ("greenhouse", "coinbase", "Coinbase"),
    ("greenhouse", "pinterest", "Pinterest"),
    ("greenhouse", "twilio", "Twilio"),
    ("greenhouse", "razorpaysoftwareprivatelimited", "Razorpay"),
    ("greenhouse", "groww", "Groww"),
    # Lever
    ("lever", "palantir", "Palantir"),
    ("lever", "spotify", "Spotify"),
    ("lever", "meesho", "Meesho"),
    ("lever", "cred", "CRED"),
    # Ashby
    ("ashby", "openai", "OpenAI"),
    ("ashby", "cohere", "Cohere"),
    ("ashby", "notion", "Notion"),
    ("ashby", "ramp", "Ramp"),
    ("ashby", "snowflake", "Snowflake"),
]

# A job must match one INTERN word AND one ROLE word in its title.
INTERN_KEYWORDS = ["intern", "interns", "internship", "trainee", "apprentice", "co-op", "coop"]

ROLE_KEYWORDS = [
    "data science", "data scientist", "machine learning", "ml", "ai",
    "artificial intelligence", "llm", "nlp", "computer vision", "deep learning",
    "generative", "genai", "applied scientist", "research engineer",
    "research scientist", "data analyst", "data engineer",
]
