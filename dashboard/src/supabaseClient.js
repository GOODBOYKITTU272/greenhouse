import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = "https://lnlvxsskkxeidlqgqqrj.supabase.co"
// The project's legacy JWT-format anon key stopped working (401 Invalid API
// key) once the Supabase project switched to the new key format — this is
// the new publishable key, meant to be public/embedded in client code just
// like this, same tier as the old anon key it replaces.
const SUPABASE_ANON_KEY = "sb_publishable_kmi9vgqtx4K8iuSHhWBQig_yBZanJoW"

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
