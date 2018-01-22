def purge_answer(plan, question_pk):
    "Delete and return the answer for the specified plan and question id"

    data = plan.data
    data.pop(question_pk, None)
    prevdata = plan.previous_data
    prevdata.pop(question_pk, None)
    plan.data = data
    plan.previous_data = prevdata
    plan.save()
    return {'data': data, 'previous_data': prevdata}
