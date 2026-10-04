import { mutate } from "@/lib/server/mutation";
import { readState,resetUser } from "@/lib/server/store";
export const runtime="nodejs";
export async function POST(request:Request) {return mutate(request,()=>null,async(q,id)=>{await resetUser(q,id);return {state:await readState(q,id)};});}
