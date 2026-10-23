"""Unit tests for deterministic fact checking, regression cases A through J, and observed failure modes."""

import pytest
from app.fact_checks import (
    extract_numbers_and_metrics,
    extract_dates_and_times,
    extract_entities,
    detect_negations,
    validate_hr_rewrite,
)


class TestFactExtraction:
    def test_extract_fraction_scores(self):
        nums = extract_numbers_and_metrics("The candidate scored 78/100 on the assessment.")
        assert "78/100" in nums
        assert "78" in nums
        assert "100" in nums

    def test_extract_percentages(self):
        nums = extract_numbers_and_metrics("The proposed increase is 6.5%, subject to approval.")
        assert "6.5%" in nums
        assert "6.5" in nums

    def test_extract_currencies(self):
        nums = extract_numbers_and_metrics("The proposed salary is ₹8,00,000 per year.")
        assert "800000" in nums

    def test_extract_counts_numerical_and_verbal(self):
        nums_digits = extract_numbers_and_metrics("The employee completed 7 of 10 assigned tasks.")
        assert "7 of 10" in nums_digits
        assert "7" in nums_digits
        assert "10" in nums_digits

        nums_words = extract_numbers_and_metrics("The candidate answered four of six technical questions correctly.")
        assert "4 of 6" in nums_words
        assert "4" in nums_words
        assert "6" in nums_words

    def test_extract_dates_and_times(self):
        dates = extract_dates_and_times("The contract is expected to run from August 1 to September 30.")
        assert "august 1" in dates
        assert "september 30" in dates

        weekdays = extract_dates_and_times("Could you please send the revised employee handbook by Friday?")
        assert "friday" in weekdays

    def test_extract_entities(self):
        entities = extract_entities("The candidate has not worked with Kubernetes for the junior developer role.")
        assert "Kubernetes" in entities


class TestRegressionCasesAThroughJ:
    """Test cases A through J as specified in the project requirements."""

    def test_case_a_observed_failure_detection(self):
        """Case A: Candidate assessment with the EXACT failure observed in initial model tests.

        Observed bad rewrite:
        'The candidate’s score is high (78/100), so they are a good fit for the junior developer role.
         The lack of experience with Kubernetes is a red flag, but it is not a showstopper if it’s not part of the role.'
        """
        original = "The candidate scored 78/100. They may be suitable for the junior developer role, but they have not worked with Kubernetes."
        bad_rewrite = (
            "The candidate’s score is high (78/100), so they are a good fit for the junior developer role. "
            "The lack of experience with Kubernetes is a red flag, but it is not a showstopper if it’s not part of the role."
        )

        res = validate_hr_rewrite(original, bad_rewrite)
        assert res.passed is False
        assert res.requires_review is True
        # Must detect the hallucinated red flag / showstopper / good fit
        assert "red flag" in res.details.unsupported_judgments or "showstopper" in res.details.unsupported_judgments
        assert res.details.possible_uncertainty_change is True
        assert any("red flag" in w.lower() for w in res.warnings)

    def test_case_a_safe_rewrite(self):
        """Case A: A valid, respectful rewrite preserving all facts, uncertainty, and negations."""
        original = "The candidate scored 78/100. They may be suitable for the junior developer role, but they have not worked with Kubernetes."
        good_rewrite = (
            "The candidate achieved a score of 78/100. While they may be suitable for the junior developer position, "
            "they have not worked with Kubernetes."
        )

        res = validate_hr_rewrite(original, good_rewrite)
        assert res.passed is True
        assert len(res.details.missing_numbers) == 0
        assert res.details.possible_negation_change is False
        assert len(res.details.unsupported_judgments) == 0

    def test_case_b_salary_and_approval(self):
        """Case B: Salary amount, currency, annual frequency, and lack of approval must be preserved."""
        original = "The proposed salary is ₹8,00,000 per year. The offer has not been approved."

        # Bad rewrite claiming it was approved or dropping the amount
        bad_rewrite = "The approved salary is ₹10,00,000 per year for the new offer."
        res_bad = validate_hr_rewrite(original, bad_rewrite)
        assert res_bad.passed is False
        assert res_bad.details.possible_negation_change is True or len(res_bad.details.missing_numbers) > 0

        # Good rewrite
        good_rewrite = "The proposed compensation is ₹8,00,000 annually. Please note that this offer has not yet been approved."
        res_good = validate_hr_rewrite(original, good_rewrite)
        assert res_good.passed is True

    def test_case_c_dates_and_uncertainty(self):
        """Case C: Contract dates August 1 to September 30, with unconfirmed status."""
        original = "The contract is expected to run from August 1 to September 30. The dates are not yet confirmed."

        # Bad rewrite that invents dates or removes uncertainty
        bad_rewrite = "The contract will run from August 1 to October 15, and the dates are confirmed."
        res_bad = validate_hr_rewrite(original, bad_rewrite)
        assert res_bad.requires_review is True
        assert res_bad.details.possible_negation_change is True or any("september 30" in w.lower() for w in res_bad.warnings)

        # Good rewrite
        good_rewrite = "The contract is anticipated to span from August 1 to September 30, though the dates are not yet confirmed."
        res_good = validate_hr_rewrite(original, good_rewrite)
        assert res_good.passed is True

    def test_case_d_performance_counts(self):
        """Case D: 7 of 10 tasks completed, remaining may be completed next week."""
        original = "The employee completed 7 of 10 assigned tasks. The remaining tasks may be completed next week."

        bad_rewrite = "The employee finished all 10 tasks and will complete the rest next week."
        res_bad = validate_hr_rewrite(original, bad_rewrite)
        assert res_bad.passed is False

        good_rewrite = "The employee has completed 7 of the 10 assigned tasks, and the remaining items may be finished next week."
        res_good = validate_hr_rewrite(original, good_rewrite)
        assert res_good.passed is True

    def test_case_e_certification_negation(self):
        """Case E: Candidate does not currently hold required certification."""
        original = "The candidate does not currently hold the required certification."

        # Bad rewrite dropping negation or turning into accusation
        bad_rewrite = "The candidate currently holds the required certification."
        res_bad = validate_hr_rewrite(original, bad_rewrite)
        assert res_bad.passed is False
        assert res_bad.details.possible_negation_change is True

        good_rewrite = "At present, the candidate does not possess the required certification."
        res_good = validate_hr_rewrite(original, good_rewrite)
        assert res_good.passed is True

    def test_case_f_interview_feedback(self):
        """Case F: four of six questions correct, system design unclear."""
        original = "The candidate answered four of six technical questions correctly. Their system design experience is unclear."

        # Bad rewrite adding unsupported recommendation
        bad_rewrite = "The candidate answered four of six technical questions correctly and is clearly unqualified."
        res_bad = validate_hr_rewrite(original, bad_rewrite)
        assert res_bad.passed is False
        assert "clearly unqualified" in res_bad.details.unsupported_judgments

        good_rewrite = "The candidate correctly answered four of six technical questions; their experience in system design remains unclear."
        res_good = validate_hr_rewrite(original, good_rewrite)
        assert res_good.passed is True

    def test_case_g_email_request(self):
        """Case G: Polite request for revised handbook by Friday."""
        original = "Could you please send the revised employee handbook by Friday?"

        # Bad rewrite turning request into directive
        bad_rewrite = "You must submit the handbook immediately."
        res_bad = validate_hr_rewrite(original, bad_rewrite)
        assert res_bad.details.speech_act_preserved is False or any("friday" in w.lower() for w in res_bad.warnings)

        good_rewrite = "Could you kindly provide the updated employee handbook by Friday?"
        res_good = validate_hr_rewrite(original, good_rewrite)
        assert res_good.passed is True

    def test_case_h_compensation_percentage(self):
        """Case H: Proposed increase 6.5%, subject to approval."""
        original = "The proposed increase is 6.5%, subject to management approval."

        # Bad rewrite changing percentage to 7% or omitting condition
        bad_rewrite = "Management has granted an approved 7.5% salary increase."
        res_bad = validate_hr_rewrite(original, bad_rewrite)
        assert res_bad.passed is False
        assert "6.5%" in res_bad.details.missing_numbers

        good_rewrite = "The recommended adjustment is 6.5%, which remains subject to management approval."
        res_good = validate_hr_rewrite(original, good_rewrite)
        assert res_good.passed is True

    def test_case_i_neutral_workplace_reminder(self):
        """Case I: Training rescheduled, new time has not been confirmed."""
        original = "The training session has been rescheduled. The new time has not been confirmed."

        bad_rewrite = "The training session has been rescheduled and the new time has been confirmed for 3 PM."
        res_bad = validate_hr_rewrite(original, bad_rewrite)
        assert res_bad.details.possible_negation_change is True

        good_rewrite = "Please note that the training session has been rescheduled; the updated time has not yet been confirmed."
        res_good = validate_hr_rewrite(original, good_rewrite)
        assert res_good.passed is True

    def test_case_j_explicit_negative(self):
        """Case J: We cannot confirm that the candidate has the required five years of experience."""
        original = "We cannot confirm that the candidate has the required five years of experience."

        bad_rewrite = "We can confirm that the candidate meets the five years of experience requirement."
        res_bad = validate_hr_rewrite(original, bad_rewrite)
        assert res_bad.passed is False
        assert res_bad.details.possible_negation_change is True

        good_rewrite = "We are unable to confirm that the candidate possesses the required five years of experience."
        res_good = validate_hr_rewrite(original, good_rewrite)
        assert res_good.passed is True


class TestPipelineAndScorecard:
    """Tests covering the 6-stage pipeline, 7 evaluation scorecard criteria, and resistance to unnecessary rewriting."""

    def test_pipeline_stages_generation(self):
        from app.fact_checks import extract_pipeline_data, analyze_robotic_language
        original = "I am writing to inform you that Alex Morgan completed the technical interview on March 12, 2026 with a score of 85 out of 100 in React."
        rewrite = "I wanted to share that Alex Morgan completed the technical interview on March 12, 2026, scoring 85 out of 100 in React."

        val = validate_hr_rewrite(original, rewrite)
        rob = analyze_robotic_language(original, rewrite)
        pipeline = extract_pipeline_data(
            original=original,
            rewrite=rewrite,
            validation=val,
            robotic_analysis=rob,
            communication_type="candidate_feedback",
            tone="professional",
            intensity="Balanced",
            context_anchor="Candidate: Alex Morgan",
        )

        # Verify all 6 stages exist and have expected data
        assert pipeline.stage_1_input["word_count"] > 0
        assert "85 out of 100" in pipeline.stage_2_intent_facts["metrics_locked"]
        assert "Alex Morgan" in pipeline.stage_2_intent_facts["entities_locked"]
        assert pipeline.stage_3_style_analysis["cliches_count"] >= 1
        assert pipeline.stage_4_contextual_rewrite["target_context"] == "Candidate Feedback"
        assert pipeline.stage_4_contextual_rewrite["context_anchor"] == "Candidate: Alex Morgan"
        assert pipeline.stage_5_meaning_check["passed"] is True
        assert "FactGuard" in pipeline.stage_6_humanized_text["certification_badge"]

    def test_categorized_robotic_findings(self):
        from app.fact_checks import analyze_robotic_language
        original = (
            "I am writing to inform you that the team will delve into candidate assessments. "
            "Please do not hesitate to reach out if you require any additional information."
        )
        rewrite = "We're excited to review candidate assessments with the team. Feel free to reach out anytime!"

        rob = analyze_robotic_language(original, rewrite)
        categories = [f.category for f in rob.findings]
        assert "Robotic AI Cliché" in categories or "Templated Opening / Closing" in categories
        assert len(rob.cliches_detected) >= 2
        assert len(rob.cliches_eliminated) >= 2

    def test_evaluation_scorecard_all_7_criteria(self):
        from app.fact_checks import calculate_evaluation_scorecard, analyze_robotic_language
        original = "The candidate scored 78/100 and worked with Python on August 10."
        good_rewrite = "The candidate achieved 78/100 and demonstrated hands-on work with Python on August 10."

        val = validate_hr_rewrite(original, good_rewrite)
        rob = analyze_robotic_language(original, good_rewrite)
        scorecard = calculate_evaluation_scorecard(
            original=original,
            rewrite=good_rewrite,
            validation=val,
            robotic_analysis=rob,
            communication_type="recruiter_notes",
            tone="professional",
        )

        assert scorecard.naturalness_score >= 90
        assert scorecard.meaning_preservation_score == 100
        assert scorecard.factuality_score == 100
        assert scorecard.contextual_tone_score >= 90
        assert scorecard.terminology_preservation_score == 100
        assert scorecard.consistency_score >= 90
        assert scorecard.resistance_score >= 90
        assert "A+" in scorecard.overall_grade

    def test_resistance_to_unnecessary_rewriting_natural_draft(self):
        from app.fact_checks import analyze_robotic_language
        natural_original = (
            "Hi Sarah, thanks for speaking with us today! We loved learning about your React experience. "
            "We'll review feedback with the team and get back to you by Friday afternoon."
        )
        rob = analyze_robotic_language(natural_original, natural_original)
        assert rob.is_already_natural is True
        assert "Zero unnecessary rewrites" in rob.resistance_note

