import { catalogIdentity,record } from "@/lib/backend-contract";
import { mutate } from "@/lib/server/mutation";
import { clearDecision, saveDecision } from "@/lib/server/store";
import type { Decision } from "@/lib/types";
export const runtime="nodejs";
export async function POST(request:Request) {return mutate(request,body=>{const r=record(body);catalogIdentity(r.id);if(r.decision!=="interested"&&r.decision!=="pass"&&r.decision!=="clear")throw new Error("Invalid decision.");return {id:r.id as string,decision:r.decision as Decision|"clear"};},async(q,user,input)=>{if(input.decision==="clear")await clearDecision(q,user,input.id);else await saveDecision(q,user,input.id,input.decision);return {saved:true};});}
