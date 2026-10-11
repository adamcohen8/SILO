"""Fixed request failure codes; never expose worker exception text or stderr."""

MESSAGES = {
    'tool_call': 'The model produced a malformed or repeated tool call. Try the request again.',
    'model_reply': 'The model returned an incomplete or invalid response. Try the request again.',
    'budget': 'The request exceeded its tool or context limits. Narrow the request.',
    'citation': 'The model omitted or invented a document citation. Try the request again.',
    'task': 'The model did not complete the requested draft or exact-citation task. No new file was saved. Try a more specific request.',
    'worker': 'The document worker failed. Restart the model and try again.',
}


def failure_code(error):
    # Only exact, fixed internal messages are classified. No document text,
    # filenames, prompts or arbitrary exception messages cross this boundary.
    message = str(error)
    if message == 'Malformed or replayed tool call':
        return 'tool_call'
    if message == 'Local model returned malformed or incomplete chat/tool data':
        return 'model_reply'
    if message in {'Requested draft proposal was not created', 'Requested exact source citation was omitted'}:
        return 'task'
    if message in {'Model call budget exhausted; no further tools executed',
                   'Tool call budget exhausted; batch was not executed',
                   'Request context exceeds the limit; narrow the document request'}:
        return 'budget'
    if message in {'Document answer omitted its verified source citation',
                   'Answer or draft contains a citation that was not read in this request',
                   'Citation has an invalid source locator',
                   'Citation locator is outside the returned source'}:
        return 'citation'
    return 'worker'
