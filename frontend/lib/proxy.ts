export function authorize(headers: Headers, token: string) {
  if (token) headers.set("Authorization", `Bearer ${token}`);
}

export function upstream(apiBase: string, parts: string[]): string {
  return `${apiBase.replace(/\/$/, "")}/${parts.join("/")}`;
}
