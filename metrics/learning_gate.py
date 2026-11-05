PROTECTED={"approval_required","never_delete_original","official_logo_stamp_immutable","semantic_crop","no_near_duplicates"}
def learning_decision(candidate_rule, comparable_posts):
    if candidate_rule in PROTECTED: return "HUMAN_REVIEW"
    if comparable_posts < 5: return "INSUFFICIENT_SAMPLE"
    return "EXPERIMENT_CANDIDATE"
