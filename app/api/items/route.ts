import { draftInput,publishKey,record } from "@/lib/backend-contract";
import { mutate } from "@/lib/server/mutation";
import { publishItem } from "@/lib/server/store";
export const runtime="nodejs";
export async function POST(request:Request) {return mutate(request,body=>{const r=record(body);return {draft:draftInput(r.draft),key:publishKey(r.key)};},async(q,id,input)=>({item:await publishItem(q,id,input.draft,input.key)}));}
