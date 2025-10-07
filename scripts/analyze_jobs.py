"""
Job Search Results Analysis Tool
Analyzes saved job search results and generates insights.
"""

import sys
from pathlib import Path
import pandas as pd
import yaml
from datetime import datetime
from collections import Counter
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class JobAnalyzer:
    """Analyzes job search results."""

    def __init__(self, config_path: str = "../config/config.yaml"):
        """Initialize with configuration."""
        self.config = self._load_config(config_path)
        self.results_dir = Path(self.config.get('output', {}).get('results_dir', '../results'))

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        return {}

    def load_latest_results(self, prefix: str = "relevant_jobs") -> pd.DataFrame:
        """Load the most recent results file."""
        csv_files = list(self.results_dir.glob(f"{prefix}_*.csv"))

        if not csv_files:
            # Try 'all_jobs' if relevant not found
            csv_files = list(self.results_dir.glob("all_jobs_*.csv"))

        if not csv_files:
            logger.error(f"No results found in {self.results_dir}")
            return pd.DataFrame()

        # Sort by modification time and get latest
        latest_file = max(csv_files, key=lambda p: p.stat().st_mtime)
        logger.info(f"Loading results from: {latest_file}")

        df = pd.read_csv(latest_file)
        return df

    def analyze_companies(self, df: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
        """Analyze top companies by job count."""
        if df.empty or 'company' not in df.columns:
            return pd.DataFrame()

        companies = df['company'].value_counts().head(top_n)
        return companies

    def analyze_locations(self, df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
        """Analyze top locations by job count."""
        if df.empty or 'location' not in df.columns:
            return pd.DataFrame()

        locations = df['location'].value_counts().head(top_n)
        return locations

    def analyze_keywords(self, df: pd.DataFrame, top_n: int = 20) -> Counter:
        """Extract and analyze keywords from job titles."""
        if df.empty or 'title' not in df.columns:
            return Counter()

        # Combine all titles
        all_titles = ' '.join(df['title'].astype(str).tolist()).lower()

        # Split into words and filter
        words = re.findall(r'\b[a-z]{3,}\b', all_titles)

        # Common stop words to filter
        stop_words = {
            'the', 'and', 'for', 'are', 'with', 'from', 'this', 'that',
            'will', 'have', 'has', 'our', 'you', 'your', 'all', 'can',
            'was', 'were', 'been', 'their', 'about', 'into', 'through',
            'job', 'work', 'position', 'role', 'opportunity'
        }

        # Filter stop words
        filtered_words = [w for w in words if w not in stop_words]

        # Count occurrences
        keyword_counts = Counter(filtered_words)
        return keyword_counts.most_common(top_n)

    def analyze_salary(self, df: pd.DataFrame) -> dict:
        """Analyze salary information if available."""
        if df.empty:
            return {}

        salary_info = {}

        if 'min_amount' in df.columns:
            salary_data = df[df['min_amount'].notna()]
            if not salary_data.empty:
                salary_info['min_avg'] = salary_data['min_amount'].mean()
                salary_info['min_median'] = salary_data['min_amount'].median()

        if 'max_amount' in df.columns:
            salary_data = df[df['max_amount'].notna()]
            if not salary_data.empty:
                salary_info['max_avg'] = salary_data['max_amount'].mean()
                salary_info['max_median'] = salary_data['max_amount'].median()

        if 'currency' in df.columns:
            salary_info['currencies'] = df['currency'].value_counts().to_dict()

        return salary_info

    def analyze_job_types(self, df: pd.DataFrame) -> pd.Series:
        """Analyze distribution of job types."""
        if df.empty or 'job_type' not in df.columns:
            return pd.Series()

        return df['job_type'].value_counts()

    def analyze_remote_distribution(self, df: pd.DataFrame) -> dict:
        """Analyze remote vs on-site distribution."""
        if df.empty or 'is_remote' not in df.columns:
            return {}

        remote_counts = df['is_remote'].value_counts().to_dict()
        return {
            'remote': remote_counts.get(True, 0),
            'on_site': remote_counts.get(False, 0)
        }

    def generate_report(self, df: pd.DataFrame):
        """Generate comprehensive analysis report."""
        if df.empty:
            print("❌ No data to analyze!")
            return

        print("\n" + "=" * 80)
        print(" " * 25 + "📊 JOB SEARCH ANALYSIS REPORT")
        print("=" * 80)

        # Overview
        print(f"\n📈 OVERVIEW")
        print(f"   Total jobs: {len(df)}")

        if 'relevance_score' in df.columns:
            print(f"   Average relevance score: {df['relevance_score'].mean():.1f}")
            print(f"   Max relevance score: {df['relevance_score'].max():.0f}")

        if 'date_posted' in df.columns:
            try:
                df['date_posted'] = pd.to_datetime(df['date_posted'], errors='coerce')
                recent_jobs = df[df['date_posted'] >= pd.Timestamp.now() - pd.Timedelta(days=7)]
                print(f"   Jobs posted in last 7 days: {len(recent_jobs)}")
            except:
                pass

        # Companies
        print(f"\n🏢 TOP COMPANIES")
        companies = self.analyze_companies(df)
        for idx, (company, count) in enumerate(companies.items(), 1):
            print(f"   {idx:2d}. {company:<40} ({count} jobs)")

        # Locations
        print(f"\n📍 TOP LOCATIONS")
        locations = self.analyze_locations(df)
        for idx, (location, count) in enumerate(locations.items(), 1):
            print(f"   {idx:2d}. {location:<40} ({count} jobs)")

        # Keywords
        print(f"\n🔑 TOP KEYWORDS IN JOB TITLES")
        keywords = self.analyze_keywords(df)
        for idx, (keyword, count) in enumerate(keywords, 1):
            print(f"   {idx:2d}. {keyword:<30} ({count} occurrences)")

        # Job types
        print(f"\n💼 JOB TYPES")
        job_types = self.analyze_job_types(df)
        for job_type, count in job_types.items():
            print(f"   {job_type:<20} {count} jobs")

        # Remote distribution
        print(f"\n🏠 REMOTE WORK DISTRIBUTION")
        remote_dist = self.analyze_remote_distribution(df)
        if remote_dist:
            total = sum(remote_dist.values())
            for work_type, count in remote_dist.items():
                pct = (count / total * 100) if total > 0 else 0
                print(f"   {work_type.capitalize():<20} {count} jobs ({pct:.1f}%)")

        # Salary info
        print(f"\n💰 SALARY INFORMATION")
        salary_info = self.analyze_salary(df)
        if salary_info:
            if 'min_avg' in salary_info:
                print(f"   Average min salary: {salary_info['min_avg']:,.0f}")
            if 'max_avg' in salary_info:
                print(f"   Average max salary: {salary_info['max_avg']:,.0f}")
            if 'currencies' in salary_info:
                print(f"   Currencies: {', '.join(salary_info['currencies'].keys())}")
        else:
            print(f"   No salary data available")

        print("\n" + "=" * 80)

    def export_filtered_by_company(self, df: pd.DataFrame, companies: list, output_file: str = None):
        """Export jobs filtered by specific companies."""
        if df.empty or 'company' not in df.columns:
            logger.warning("No data or company column not found")
            return

        filtered = df[df['company'].isin(companies)]

        if filtered.empty:
            logger.warning(f"No jobs found for companies: {companies}")
            return

        if output_file is None:
            output_file = self.results_dir / "filtered_by_company.csv"

        filtered.to_csv(output_file, index=False)
        print(f"\n💾 Filtered {len(filtered)} jobs saved to: {output_file}")

    def export_top_scoring_jobs(self, df: pd.DataFrame, top_n: int = 50, output_file: str = None):
        """Export top N jobs by relevance score."""
        if df.empty or 'relevance_score' not in df.columns:
            logger.warning("No data or relevance_score column not found")
            return

        top_jobs = df.nlargest(top_n, 'relevance_score')

        if output_file is None:
            output_file = self.results_dir / f"top_{top_n}_jobs.csv"

        top_jobs.to_csv(output_file, index=False)
        print(f"\n💾 Top {top_n} jobs saved to: {output_file}")


def main():
    """Main entry point."""
    # Allow custom config path via command line
    config_path = sys.argv[1] if len(sys.argv) > 1 else "../config/config.yaml"

    analyzer = JobAnalyzer(config_path)

    # Load latest results
    df = analyzer.load_latest_results(prefix="relevant_jobs")

    if df.empty:
        logger.error("No results to analyze. Run search_jobs.py first.")
        sys.exit(1)

    # Generate report
    analyzer.generate_report(df)

    # Optional: Export top scoring jobs
    if 'relevance_score' in df.columns:
        analyzer.export_top_scoring_jobs(df, top_n=50)

    # Optional: Filter by companies (customize as needed)
    # target_companies = ['Google', 'Meta', 'ETH Zurich']
    # analyzer.export_filtered_by_company(df, target_companies)


if __name__ == "__main__":
    main()
