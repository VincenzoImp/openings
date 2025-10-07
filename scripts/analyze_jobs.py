#!/usr/bin/env python3
"""
Job Analysis Tool
Analyzes saved job search results and generates insights
"""

import pandas as pd
import glob
import os
from collections import Counter
import matplotlib.pyplot as plt
import seaborn as sns


def load_latest_results():
    """Load the most recent job search results"""
    results_dir = '../results'

    if not os.path.exists(results_dir):
        print("❌ No results directory found. Run search_jobs.py first.")
        return None

    # Find latest CSV file
    csv_files = glob.glob(f'{results_dir}/relevant_jobs_*.csv')

    if not csv_files:
        csv_files = glob.glob(f'{results_dir}/all_jobs_*.csv')

    if not csv_files:
        print("❌ No job results found. Run search_jobs.py first.")
        return None

    latest_file = max(csv_files, key=os.path.getctime)
    print(f"📂 Loading: {latest_file}")

    df = pd.read_csv(latest_file)
    print(f"✅ Loaded {len(df)} jobs")

    return df


def analyze_companies(df):
    """Analyze companies hiring"""
    print("\n" + "=" * 80)
    print("🏢 TOP COMPANIES HIRING")
    print("=" * 80)

    company_counts = df['company'].value_counts().head(15)

    for company, count in company_counts.items():
        print(f"  {company}: {count} positions")

    return company_counts


def analyze_locations(df):
    """Analyze job locations"""
    print("\n" + "=" * 80)
    print("📍 JOB LOCATIONS")
    print("=" * 80)

    location_counts = df['location'].value_counts().head(10)

    for location, count in location_counts.items():
        print(f"  {location}: {count} jobs")

    return location_counts


def analyze_keywords(df):
    """Extract and analyze common keywords"""
    print("\n" + "=" * 80)
    print("🔑 MOST COMMON KEYWORDS IN JOB TITLES")
    print("=" * 80)

    # Combine all titles
    all_titles = ' '.join(df['title'].dropna().astype(str).str.lower())

    # Split into words and count
    words = all_titles.split()

    # Filter out common words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'at', 'to', 'for',
                  'of', 'on', 'with', 'by', 'from', 'is', 'are', 'was', 'be', '-'}

    filtered_words = [word for word in words if word not in stop_words and len(word) > 2]

    word_counts = Counter(filtered_words).most_common(20)

    for word, count in word_counts:
        print(f"  {word}: {count}")

    return word_counts


def analyze_salary(df):
    """Analyze salary information if available"""
    print("\n" + "=" * 80)
    print("💰 SALARY INFORMATION")
    print("=" * 80)

    if 'min_amount' in df.columns:
        salary_data = df[df['min_amount'].notna()]

        if len(salary_data) > 0:
            print(f"  Jobs with salary info: {len(salary_data)}")
            print(f"  Average min salary: {salary_data['min_amount'].mean():.0f}")
            print(f"  Average max salary: {salary_data['max_amount'].mean():.0f}")

            if 'currency' in df.columns:
                currencies = salary_data['currency'].value_counts()
                print(f"\n  Currencies:")
                for curr, count in currencies.items():
                    print(f"    {curr}: {count} jobs")
        else:
            print("  ⚠️ No salary information available in results")
    else:
        print("  ⚠️ No salary data in results")


def generate_report(df):
    """Generate a comprehensive analysis report"""

    print("""
    ╔════════════════════════════════════════════════════════════════════╗
    ║                    JOB SEARCH ANALYSIS REPORT                      ║
    ╚════════════════════════════════════════════════════════════════════╝
    """)

    print(f"\n📊 OVERVIEW")
    print(f"  Total jobs analyzed: {len(df)}")

    if 'relevance_score' in df.columns:
        print(f"  Average relevance score: {df['relevance_score'].mean():.1f}")
        print(f"  Highest relevance score: {df['relevance_score'].max():.0f}")

    if 'search_date' in df.columns:
        print(f"  Search date: {df['search_date'].iloc[0]}")

    # Analyze different aspects
    analyze_companies(df)
    analyze_locations(df)
    analyze_keywords(df)
    analyze_salary(df)

    # Job types
    if 'job_type' in df.columns:
        print("\n" + "=" * 80)
        print("💼 JOB TYPES")
        print("=" * 80)
        job_types = df['job_type'].value_counts()
        for jtype, count in job_types.items():
            print(f"  {jtype}: {count}")

    # Remote opportunities
    if 'is_remote' in df.columns:
        print("\n" + "=" * 80)
        print("🏠 REMOTE WORK OPTIONS")
        print("=" * 80)
        remote_counts = df['is_remote'].value_counts()
        for remote, count in remote_counts.items():
            print(f"  {'Remote' if remote else 'On-site'}: {count} jobs")


def export_filtered_by_company(df, companies):
    """Export jobs filtered by specific companies"""
    if not companies:
        return

    print(f"\n🔍 Filtering jobs from: {', '.join(companies)}")

    filtered = df[df['company'].isin(companies)]

    if len(filtered) > 0:
        output_path = '../results/filtered_by_company.csv'
        filtered.to_csv(output_path, index=False)
        print(f"💾 Saved {len(filtered)} jobs to: {output_path}")
    else:
        print("⚠️ No jobs found from specified companies")


def main():
    """Main analysis function"""

    df = load_latest_results()

    if df is None:
        return

    generate_report(df)

    # Optional: Filter by specific companies of interest
    # Uncomment and customize this list:
    # target_companies = ['Google', 'ETH Zurich', 'EPFL', 'IBM Research']
    # export_filtered_by_company(df, target_companies)

    print("\n" + "=" * 80)
    print("✅ Analysis complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
