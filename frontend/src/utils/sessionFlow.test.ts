import { describe, expect, it } from 'vitest';
import {
  mergePersistedMessagesWithLiveTurns,
  resolveChatTarget,
  resolveRenderSessionId,
} from './sessionFlow';


describe('chat session flow', () => {
  it('allows the backend to create the first project and session', () => {
    expect(resolveChatTarget(null, null, [])).toEqual({
      projectId: null,
      sessionId: null,
    });
  });

  it('creates a new session without sending the local render id', () => {
    expect(
      resolveChatTarget(
        'project-1',
        null,
        [{ id: 'project-1' }],
      ),
    ).toEqual({
      projectId: 'project-1',
      sessionId: null,
    });
  });

  it('keeps a local render key until backend metadata arrives', () => {
    expect(resolveRenderSessionId(null, 'local-1')).toBe('local-1');
    expect(resolveRenderSessionId('session-1', 'local-1')).toBe('session-1');
  });

  it('matches repeated content to the latest persisted exchange', () => {
    const messages = [
      { id: 'message-1', role: 'user', content: 'same' },
      { id: 'message-2', role: 'assistant', content: 'old answer' },
      { id: 'message-3', role: 'user', content: 'same' },
      { id: 'message-4', role: 'assistant', content: 'new answer' },
    ];
    const turns = [
      { id: 'turn-1', role: 'user', content: 'same' },
      { id: 'turn-2', role: 'assistant', content: 'new answer', pending: false },
    ];

    expect(mergePersistedMessagesWithLiveTurns(messages, turns)).toEqual([
      messages[0],
      messages[1],
      turns[0],
      turns[1],
    ]);
  });

  it('keeps live turns at their persisted chronological positions', () => {
    const messages = [
      { id: 'message-1', role: 'user', content: 'first question' },
      { id: 'message-2', role: 'assistant', content: 'first answer' },
      { id: 'message-3', role: 'user', content: 'second question' },
      { id: 'message-4', role: 'assistant', content: 'second answer' },
    ];
    const turns = [
      { id: 'turn-1', role: 'user', content: 'first question' },
      {
        id: 'turn-2',
        role: 'assistant',
        content: 'first answer',
        attachments: [{ type: 'evidence' }],
      },
    ];

    expect(mergePersistedMessagesWithLiveTurns(messages, turns)).toEqual([
      turns[0],
      turns[1],
      messages[2],
      messages[3],
    ]);
  });

  it('appends unpersisted and pending turns after persisted history', () => {
    const messages = [
      { id: 'message-1', role: 'user', content: 'first question' },
      { id: 'message-2', role: 'assistant', content: 'first answer' },
    ];
    const turns = [
      { id: 'turn-1', role: 'user', content: 'first question' },
      { id: 'turn-2', role: 'assistant', content: 'first answer' },
      { id: 'turn-3', role: 'user', content: 'second question' },
      { id: 'turn-4', role: 'assistant', content: '', pending: true },
    ];

    expect(mergePersistedMessagesWithLiveTurns(messages, turns)).toEqual(turns);
  });
});
