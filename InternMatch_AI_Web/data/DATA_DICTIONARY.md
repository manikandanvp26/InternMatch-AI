# Data Dictionary

## student_training_data.csv
- education: education category
- domain_interest: preferred technical domain
- career_goal: desired career role
- projects_count: number of completed projects (synthetic)
- certifications_count: number of certifications (synthetic)
- experience_level: experience category (synthetic)
- skills_count: number of skills (synthetic)
- internship_category: synthetic target label for model training

## internships.csv
- internship_id: project-local row identifier
- title/company: role and organization/provider as shown by the source page
- category: manually mapped project category
- location/work_mode/duration_months: extracted or normalized listing attributes
- required_skills: summarized skill terms for matching; not a full job description
- preferred_education/stipend: available summary or verification note
- source_url/source_type/source_checked: provenance fields
- notes: caveat for checking status and conditions
