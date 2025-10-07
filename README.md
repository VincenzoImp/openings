# JobSearch Tool

A flexible, configuration-driven job search tool that scrapes multiple job sites (LinkedIn, Indeed, Glassdoor, Google Jobs) and scores results based on your customizable relevance criteria.

## Features

- 🔍 **Multi-Site Search**: Search across LinkedIn, Indeed, Glassdoor, and Google Jobs simultaneously
- ⚙️ **Fully Configurable**: All search parameters, queries, and scoring weights defined in YAML config files
- 🎯 **Smart Relevance Scoring**: Define keyword categories with custom weights to score jobs by relevance
- 📊 **Built-in Analysis**: Analyze results with detailed reports on companies, locations, keywords, salaries
- 🐳 **Docker Support**: Run in isolated container environment
- 📁 **Multiple Output Formats**: Export results as CSV and Excel with auto-formatting
- 🔄 **Deduplication**: Automatically removes duplicate job postings
- ♻️ **Retry Logic**: Configurable retry for failed queries

## Quick Start

### Prerequisites

- Python 3.10+ OR Docker
- Git

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd jobsearch-tool
```

2. Copy the example configuration:
```bash
cp config/config.example.yaml config/config.yaml
```

3. Edit `config/config.yaml` with your profile, target locations, search queries, and relevance scoring preferences.

### Running the Tool

#### Option 1: Using Docker (Recommended)

```bash
# Build and run
docker compose up --build

# Run in background
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

#### Option 2: Using Local Python

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run job search
cd scripts
python search_jobs.py

# Analyze results
python analyze_jobs.py
```

### Using Custom Configuration

```bash
# With Docker (mount custom config)
docker compose run jobsearch python search_jobs.py ../config/my_custom_config.yaml

# With local Python
python search_jobs.py ../config/my_custom_config.yaml
```

## Configuration

The tool is entirely configuration-driven. All parameters are defined in a YAML configuration file.

### Configuration Sections

#### 1. Profile
Define your background for display purposes:

```yaml
profile:
  name: "Your Name"
  email: "your.email@example.com"
  summary: |
    Brief description of your background
  career_stage: "Software Engineer"
  target_start_date: "2026-06"
```

#### 2. Search Parameters
Define where and what to search:

```yaml
search:
  sites:
    - indeed
    - linkedin
    - google

  locations:
    - "Berlin, Germany"
    - "Amsterdam, Netherlands"

  queries:
    backend:
      - "backend engineer"
      - "Python developer"

    data_science:
      - "data scientist"
      - "machine learning engineer"

  filters:
    results_per_query: 50
    days_back: 30
    job_types:
      - fulltime
      - contract
```

#### 3. Relevance Scoring
Define keyword categories and their weights:

```yaml
relevance_scoring:
  min_score: 10

  categories:
    primary_skills:
      weight: 20
      keywords:
        - "distributed systems"
        - "Python"
        - "machine learning"

    seniority:
      weight: 15
      keywords:
        - "senior"
        - "lead"
        - "staff"
```

**How Scoring Works:**
- Each job is scored based on keyword matches in title, description, company, and location
- If ANY keyword from a category matches, that category's weight is added to the score
- Jobs with scores below `min_score` are filtered out
- Higher scores = more relevant to your profile

#### 4. Output Settings

```yaml
output:
  results_dir: "../results"
  formats:
    - csv
    - xlsx
  prefix: "jobs"
  include_timestamp: true
```

#### 5. Advanced Settings

```yaml
advanced:
  deduplication_fields:
    - title
    - company
    - location
  retry_failed_queries: true
  max_retries: 2
  rate_limit_delay: 1
  log_level: "INFO"
  save_all_jobs: true
  save_relevant_jobs: true
```

## Example Configurations

The `examples/` directory contains pre-configured templates:

### 1. PhD Researcher (Vincenzo's Configuration)
```bash
cp examples/vincenzo_config.yaml config/config.yaml
```
- Focus: Research positions, blockchain, distributed systems
- Locations: Switzerland (Zurich, Lausanne, Geneva)
- Keywords: PhD, postdoc, research scientist, ETH, EPFL

### 2. Software Engineer
```bash
cp examples/software_engineer_config.yaml config/config.yaml
```
- Focus: Backend/full-stack engineering roles
- Locations: European tech hubs (Berlin, Amsterdam, London)
- Keywords: Senior, lead, Python, Go, cloud, Kubernetes

### Creating Your Own Configuration

1. Start with `config.example.yaml`
2. Customize the following sections:
   - **Profile**: Your name, career stage, target start date
   - **Locations**: Cities/countries you want to work in
   - **Queries**: Job titles and roles you're seeking (organize by category)
   - **Relevance Scoring**: Keywords that matter to you, with weights reflecting importance

**Tips:**
- Group queries by category for better organization
- Higher weights (15-25) for must-have skills/requirements
- Medium weights (8-15) for nice-to-have skills
- Lower weights (3-8) for secondary preferences
- Set `min_score` to filter out irrelevant jobs (10-15 recommended)

## Output Files

Results are saved to the `results/` directory:

```
results/
├── all_jobs_20250107_143022.csv          # All jobs found
├── all_jobs_20250107_143022.xlsx         # Excel version
├── relevant_jobs_20250107_143022.csv     # Filtered by relevance score
├── relevant_jobs_20250107_143022.xlsx    # Excel version
└── top_50_jobs.csv                       # Top 50 by score (from analyze script)
```

## Analysis Tool

After running a search, analyze the results:

```bash
cd scripts
python analyze_jobs.py
```

The analysis report includes:
- 📈 Overview (total jobs, average score, recent postings)
- 🏢 Top companies by job count
- 📍 Top locations
- 🔑 Most common keywords in job titles
- 💼 Job type distribution (fulltime, contract, etc.)
- 🏠 Remote vs on-site breakdown
- 💰 Salary information (if available)

### Custom Analysis Functions

```python
from analyze_jobs import JobAnalyzer

analyzer = JobAnalyzer("../config/config.yaml")
df = analyzer.load_latest_results()

# Export jobs from specific companies
analyzer.export_filtered_by_company(df, ['Google', 'Meta', 'Apple'])

# Export top 100 jobs by score
analyzer.export_top_scoring_jobs(df, top_n=100)
```

## Project Structure

```
jobsearch-tool/
├── config/
│   ├── config.example.yaml       # Template configuration
│   └── config.yaml               # Your configuration (gitignored)
├── scripts/
│   ├── search_jobs.py            # Main search script
│   └── analyze_jobs.py           # Analysis tool
├── examples/
│   ├── vincenzo_config.yaml      # PhD researcher example
│   └── software_engineer_config.yaml  # Software engineer example
├── results/                      # Output directory (gitignored)
│   └── .gitkeep
├── docs/                         # Additional documentation
├── Dockerfile                    # Docker container definition
├── docker-compose.yml            # Docker Compose configuration
├── requirements.txt              # Python dependencies
├── .gitignore
├── LICENSE
└── README.md
```

## Troubleshooting

### No Jobs Found

**Possible causes:**
1. **Rate limiting**: Job sites may be blocking requests
   - Solution: Reduce `results_per_query` from 50 to 20-30
   - Increase `rate_limit_delay` to 2-3 seconds
   - Wait a few hours before re-running

2. **Queries too specific**: Narrow queries return fewer results
   - Solution: Add broader queries (e.g., "software engineer" vs "senior Rust blockchain engineer")

3. **Location format**: Some locations may not be recognized
   - Solution: Try "City, Country" format (e.g., "Berlin, Germany")

### Python Version Error

**Error**: `Could not find a version that satisfies the requirement python-jobspy`

**Cause**: JobSpy requires Python 3.10+

**Solution**: Use Docker OR upgrade Python:
```bash
# Check Python version
python3 --version

# Install Python 3.11 (macOS)
brew install python@3.11
```

### Docker Issues

```bash
# Clear Docker cache and rebuild
docker compose down
docker system prune -f
docker compose up --build
```

### Glassdoor Errors

Glassdoor API frequently returns 400 errors. This is normal - the tool will still find jobs from LinkedIn, Indeed, and Google Jobs.

## Advanced Usage

### Scheduled Searches

Run automated weekly searches using cron (Linux/macOS):

```bash
# Edit crontab
crontab -e

# Add weekly search (every Friday at 9 AM)
0 9 * * 5 cd /path/to/jobsearch-tool && docker compose up
```

### Multiple Configurations

Maintain separate configurations for different job searches:

```bash
# Search for research positions
python search_jobs.py ../config/research_config.yaml

# Search for industry positions
python search_jobs.py ../config/industry_config.yaml
```

### Filtering Results

```python
import pandas as pd

# Load results
df = pd.read_csv('../results/relevant_jobs_20250107.csv')

# Filter by location
zurich_jobs = df[df['location'].str.contains('Zurich', case=False)]

# Filter by company
tech_companies = ['Google', 'Meta', 'Apple', 'Microsoft']
tech_jobs = df[df['company'].isin(tech_companies)]

# Filter by score threshold
high_scoring = df[df['relevance_score'] >= 30]

# Export filtered results
high_scoring.to_csv('../results/high_scoring_jobs.csv', index=False)
```

## Configuration Best Practices

1. **Start Broad**: Begin with general queries, then refine based on results
2. **Test Incrementally**: Test with 1-2 locations first, then expand
3. **Tune Scoring**: Run a search, review results, adjust weights
4. **Organize Queries**: Group related queries by category for maintainability
5. **Version Control**: Keep configuration files in git (but gitignore `config.yaml` if it contains personal info)

## Performance Tips

### Optimize Search Time
- **Reduce queries**: Focus on high-value search terms
- **Limit locations**: Start with 2-3 key cities
- **Lower results_per_query**: 20-30 instead of 50
- **Increase rate_limit_delay**: Prevents rate limiting (1-2 seconds recommended)

### Improve Result Quality
- **Tune relevance scoring**: Higher weights for must-have skills, lower for nice-to-haves
- **Increase min_score**: Filter out noise (try 15-20 for stricter filtering)
- **Add negative keywords**: Coming soon - penalize jobs with unwanted terms
- **Company whitelist**: Use `export_filtered_by_company()` in analysis script

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - See LICENSE file for details.

## Support

For issues or questions:
- GitHub Issues: [Report a bug or request a feature]
- Email: [Your support email]

## Acknowledgments

- Built with [JobSpy](https://github.com/speedyapply/JobSpy) - Job scraping library
- Uses pandas, openpyxl, PyYAML for data processing

---

**Note**: This tool is for personal job search purposes only. Be respectful of job sites' terms of service and rate limits. Do not run excessive searches or use for commercial scraping.
