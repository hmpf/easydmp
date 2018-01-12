def purge_answer(plan, question_pk):
    "Delete and return the answer for the specified plan and question id"

    data = plan.data.pop(question_pk, None)
    prevdata = plan.previous_data.pop(question_pk, None)
    plan.save()
    return {'data': data, 'previous_data': prevdata}
