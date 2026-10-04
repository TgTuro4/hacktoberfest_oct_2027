import { profileInput } from "@/lib/backend-contract";
import { mutate } from "@/lib/server/mutation";
import { saveProfile } from "@/lib/server/store";
export const runtime="nodejs";
export async function POST(request:Request) {return mutate(request,profileInput,async(q,id,input)=>({profile:await saveProfile(q,id,input)}));}
