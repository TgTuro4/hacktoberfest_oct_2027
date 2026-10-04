import "server-only";
export const reply = (value: unknown,status=200)=>Response.json(value,{status,headers:{"Cache-Control":"no-store"}});
export function sameOrigin(request: Request) {
  const origin=request.headers.get("origin");
  if (!origin || origin !== new URL(request.url).origin) throw new Error("Invalid request origin.");
}
export async function readJson(request: Request, limit=32000): Promise<unknown> {
  if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json") || !request.body) throw new Error("Send JSON.");
  const reader=request.body.getReader(); let size=0; const chunks:Uint8Array[]=[];
  try { for(;;) { const chunk=await reader.read(); if(chunk.done)break; size+=chunk.value.byteLength; if(size>limit){await reader.cancel();throw new Error("Request too large.");} chunks.push(chunk.value); } }
  finally { reader.releaseLock(); }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}
