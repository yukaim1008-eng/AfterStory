export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch("/api" + path, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(180000),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || "connection_failed");
  }
  return response.json();
}
export function errorText(error: unknown) {
  const code = error instanceof Error ? error.message : "";
  return (
    (
      {
        conversation_busy: "上一条消息仍在处理，稍后重试即可。",
        llm_key_missing: "尚未配置模型密钥，请在本地配置中填写后重启服务。",
        llm_timeout: "这次回复等待时间较长，消息已保留，可以重试。",
        llm_http_error:
          "模型服务暂时无法回复，请检查模型配置与可用额度后重试。",
        stale_turn_retry: "这条消息之后已有新对话，请重新输入发送。",
        character_version_not_found:
          "角色联调资料尚未导入，请先运行角色导入命令。",
        provider_unavailable: "暂时没有收到回复。消息已保留，可以重试。",
        database_unavailable: "暂时连接不上聊天记录，请检查本地数据库。",
      } as Record<string, string>
    )[code] || "连接暂时中断，内容已保留，请稍后重试。"
  );
}
