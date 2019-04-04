# -*- coding: utf-8 -*-

from copy import deepcopy
import logging


LOG = logging.getLogger(__name__)
LOG_MESSAGE_QUESTION_CHANGE = "Changed q%s from %s to %s"


def convert_simple_answers(data, mapping, question_ids, verbose=True):
    if not data:
        LOG.debug("No data, skipping answer conversion")
        return data
    data = deepcopy(data)
    question_ids = [str(qid) for qid in question_ids]
    for qid, choice in tuple(data.items()):
        if not (qid in question_ids and choice):
            LOG.debug('Skipping q%s', qid)
            continue
        v = choice['choice']
        try:
            if v in mapping.keys():
                old_v = v
                v = mapping[v]
                data[qid]['choice'] = v
                LOG.debug(LOG_MESSAGE_QUESTION_CHANGE,
                    qid, repr(old_v), repr(v)
                )
                if verbose:
                    print(LOG_MESSAGE_QUESTION_CHANGE % qid, repr(old_v), repr(v))
        except TypeError:
            # v is not a simple answer
            pass
    return data


def bool_to_yesno(data, question_ids, verbose=True):
    mapping = {True: 'Yes', False: 'No'}
    return convert_simple_answers(data, mapping, question_ids, verbose)


def yesno_to_bool(data, question_ids, verbose=True):
    mapping = {'Yes': True, 'No': False}
    return convert_simple_answers(data, mapping, question_ids, verbose)


def convert_plan_answers(func, question_ids, plans, verbose=True):
    func_name = func.__name__
    LOG.info('About to convert plan answers, conversion "%s"', func_name)
    for plan in plans:
        change = False
        if verbose: print('Processing plan {}'.format(plan.id))
        data = plan.data.copy()
        new_data = func(data, question_ids, verbose)
        if data != new_data:
            plan.data = new_data
            change = True
        previous_data = plan.previous_data.copy()
        new_previous_data = func(previous_data, question_ids, verbose)
        if previous_data != new_previous_data:
            plan.previous_data = new_previous_data
            change = True
        if change:
            plan.save()
            if verbose: print('Saved changes to plan {}'.format(plan.id))
            LOG.info('Successfully converted answers of plan %s', plan.id)
