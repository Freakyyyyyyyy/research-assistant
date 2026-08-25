interface ProjectRef {
  id: string;
}

export interface ChatTarget {
  projectId: string | null;
  sessionId: string | null;
}


export function resolveChatTarget(
  activeProjectId: string | null,
  activeSessionId: string | null,
  projects: ProjectRef[],
): ChatTarget {
  if (activeProjectId) {
    return {
      projectId: activeProjectId,
      sessionId: activeSessionId,
    };
  }
  return {
    projectId: projects[0]?.id ?? null,
    sessionId: null,
  };
}


export function resolveRenderSessionId(
  backendSessionId: string | null,
  localSessionId: string,
): string {
  return backendSessionId ?? localSessionId;
}


interface MessageLike {
  role: string;
  content: string;
}

interface TurnLike extends MessageLike {
  pending?: boolean;
}


export function mergePersistedMessagesWithLiveTurns<
  TMessage extends MessageLike,
  TTurn extends TurnLike,
>(messages: TMessage[], turns: TTurn[]): Array<TMessage | TTurn> {
  const turnIndexesByContent = new Map<string, number[]>();
  for (let index = 0; index < turns.length; index += 1) {
    const turn = turns[index];
    if (turn.pending || !turn.content) continue;
    const key = `${turn.role}\u0000${turn.content}`;
    const indexes = turnIndexesByContent.get(key) ?? [];
    indexes.push(index);
    turnIndexesByContent.set(key, indexes);
  }

  const replacementByMessageIndex = new Map<number, number>();
  const matchedTurnIndexes = new Set<number>();
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    const key = `${message.role}\u0000${message.content}`;
    const indexes = turnIndexesByContent.get(key);
    const turnIndex = indexes?.pop();
    if (turnIndex === undefined) continue;
    replacementByMessageIndex.set(index, turnIndex);
    matchedTurnIndexes.add(turnIndex);
  }

  const merged: Array<TMessage | TTurn> = messages.map((message, index) => {
    const turnIndex = replacementByMessageIndex.get(index);
    return turnIndex === undefined ? message : turns[turnIndex];
  });
  for (let index = 0; index < turns.length; index += 1) {
    if (!matchedTurnIndexes.has(index)) merged.push(turns[index]);
  }
  return merged;
}
