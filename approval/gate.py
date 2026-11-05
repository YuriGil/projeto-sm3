VALID={"APROVAR":"APROVADO","REVISAR":"REVISAR","DESCARTAR":"DESCARTAR"}
def apply_decision(content, decision, feedback=""):
    if decision not in VALID: raise ValueError("INVALID_APPROVAL_DECISION")
    x=dict(content); x["approval_decision"]=decision; x["status"]=VALID[decision]; x["feedback"]=feedback
    x["publish_eligible"]=decision=="APROVAR"
    return x
