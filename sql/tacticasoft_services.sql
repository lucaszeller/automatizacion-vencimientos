SELECT
    e.Empresa AS cliente,
    ns.Numero AS equipo,
    ns.Numero AS serial,
    COALESCE(STR_TO_DATE(NULLIF(i.Campo2, ''), '%d/%m/%Y'), s.Fecha, s.FechaCreacion) AS fecha_service,
    CAST(s.Numero AS CHAR) AS numero_soporte,
    NULLIF(i.Campo1, '') AS horas,
    NULL AS tipo_service,
    NULLIF(i.Campo4, '') AS lugar,
    COALESCE(NULLIF(c.Correo, ''), NULLIF(dc_contacto.Direccion, ''), NULLIF(dc_empresa.Direccion, '')) AS mail_cliente,
    NULLIF(tf_contacto.Numero, '') AS telefono_cliente,
    CONCAT_WS(' ', s.Problema, s.Solucion, s.Notas) AS observaciones
FROM soporte s
LEFT JOIN info i
    ON i.IDRef = s.RecID
LEFT JOIN empresas e
    ON e.IDEmpresa = s.IDEmpresa
LEFT JOIN contactos c
    ON c.IDContacto = s.IDContacto
LEFT JOIN direccionescorreo dc_contacto
    ON dc_contacto.IDRef = c.IDContacto AND dc_contacto.Defecto = 1
LEFT JOIN direccionescorreo dc_empresa
    ON dc_empresa.IDRef = s.IDEmpresa AND dc_empresa.Defecto = 1
LEFT JOIN telefonos tf_contacto
    ON tf_contacto.IDRef2 = c.IDContacto AND tf_contacto.Defecto = 1
LEFT JOIN productosstocknroserie ns
    ON ns.RecID = s.IDNroSerie
WHERE LOWER(COALESCE(s.Problema, '')) REGEXP '(^|[[:space:]-])(servicio|service)[[:space:]]+(preventivo|[0-9])'
  AND COALESCE(s.Fecha, s.FechaCreacion) >= DATE_SUB(CURDATE(), INTERVAL 36 MONTH)
  AND ns.Numero IS NOT NULL
ORDER BY ns.Numero, COALESCE(STR_TO_DATE(NULLIF(i.Campo2, ''), '%d/%m/%Y'), s.Fecha, s.FechaCreacion);
