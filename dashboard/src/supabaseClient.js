import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = "https://lnlvxsskkxeidlqgqqrj.supabase.co"
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc5MzkxNjUsImV4cCI6MjEwMzUxNTE2NX0.0yvxG0uJXDYUQqPXRlFG_DAxpm6Ln0EsY-X1HdtFByc"

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
