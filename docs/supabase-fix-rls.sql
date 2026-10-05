ALTER TABLE perfiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Usuarios ven su propio perfil" ON perfiles;
DROP POLICY IF EXISTS "Usuarios crean su perfil" ON perfiles;
DROP POLICY IF EXISTS "Usuarios actualizan su perfil" ON perfiles;
DROP POLICY IF EXISTS "Usuarios actualizan su propio perfil" ON perfiles;
DROP POLICY IF EXISTS "Admin ve todos los perfiles" ON perfiles;
DROP POLICY IF EXISTS "select_own" ON perfiles;
DROP POLICY IF EXISTS "insert_own" ON perfiles;
DROP POLICY IF EXISTS "update_own" ON perfiles;
DROP POLICY IF EXISTS "delete_own" ON perfiles;

CREATE POLICY "select_own" ON perfiles
  FOR SELECT
  USING (auth.uid() = id);
CREATE POLICY "insert_own" ON perfiles
  FOR INSERT
  WITH CHECK (auth.uid() = id);

CREATE POLICY "update_own" ON perfiles
  FOR UPDATE
  USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id); 
CREATE POLICY "delete_own" ON perfiles
  FOR DELETE
  USING (auth.uid() = id);

SELECT 'Políticas RLS de perfiles corregidas y aplicadas correctamente.' AS resultado;