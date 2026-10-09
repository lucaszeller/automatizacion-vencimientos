SELECT
    e.IDEmpresa AS id_empresa,
    e.Empresa AS cliente,
    ns.Numero AS equipo,
    ns.Numero AS serial,
    -- Datos reales del equipo (solapa Info del Nro de Serie en Tactica).
    -- Viven en la tabla info, colgados del registro de compra del equipo:
    --   productosstocknroserie <- compraproductos.IDNroSerie <- info.IDRef
    --     Campo1 = MARCA    Campo2 = MODELO    Campo5 = SERIE
    -- ns.Numero ("HELI Nº 1 (3246)") es el identificador interno de Tactica,
    -- NO la serie ni el modelo del equipo.
    (
        SELECT NULLIF(TRIM(i2.Campo5), '')
        FROM compraproductos cp
        INNER JOIN info i2 ON i2.IDRef = cp.RecID
        WHERE cp.IDNroSerie = ns.RecID
          AND NULLIF(TRIM(i2.Campo5), '') IS NOT NULL
        ORDER BY cp.FechaCompra DESC, cp.RecID DESC
        LIMIT 1
    ) AS serie_equipo,
    (
        SELECT NULLIF(TRIM(i2.Campo1), '')
        FROM compraproductos cp
        INNER JOIN info i2 ON i2.IDRef = cp.RecID
        WHERE cp.IDNroSerie = ns.RecID
          AND NULLIF(TRIM(i2.Campo5), '') IS NOT NULL
        ORDER BY cp.FechaCompra DESC, cp.RecID DESC
        LIMIT 1
    ) AS marca_equipo,
    (
        SELECT NULLIF(TRIM(i2.Campo2), '')
        FROM compraproductos cp
        INNER JOIN info i2 ON i2.IDRef = cp.RecID
        WHERE cp.IDNroSerie = ns.RecID
          AND NULLIF(TRIM(i2.Campo5), '') IS NOT NULL
        ORDER BY cp.FechaCompra DESC, cp.RecID DESC
        LIMIT 1
    ) AS modelo_equipo,
    -- Usar Campo2 solo si su año coincide con el de s.Fecha (evita typos de año como 2024 en vez de 2025)
    CASE
        WHEN STR_TO_DATE(NULLIF(i.Campo2, ''), '%d/%m/%Y') IS NOT NULL
             AND YEAR(STR_TO_DATE(NULLIF(i.Campo2, ''), '%d/%m/%Y')) = YEAR(COALESCE(s.Fecha, s.FechaCreacion))
        THEN STR_TO_DATE(NULLIF(i.Campo2, ''), '%d/%m/%Y')
        ELSE COALESCE(s.Fecha, s.FechaCreacion)
    END AS fecha_service,
    CAST(s.Numero AS CHAR) AS numero_soporte,
    NULLIF(i.Campo1, '') AS horas,
    NULL AS tipo_service,
    NULLIF(i.Campo4, '') AS lugar,
    COALESCE(NULLIF(c.Correo, ''), NULLIF(dc_contacto.Direccion, ''), NULLIF(dc_empresa.Direccion, '')) AS mail_cliente,
    -- Prioridad:
    -- 1. Celular (Tipo=0) de contacto de la empresa con cargo que contenga "wpp"
    -- 2. Celular (Tipo=0) del contacto asignado al soporte
    -- 3. Celular (Tipo=0) de cualquier contacto de la empresa
    -- 4. Cualquier telefono del contacto asignado al soporte
    COALESCE(
        (
            SELECT NULLIF(tf.Numero, '')
            FROM telefonos tf
            INNER JOIN contactos c2 ON c2.IDContacto = tf.IDRef2
            WHERE c2.IDEmpresa = e.IDEmpresa
              AND LOWER(c2.Cargo) LIKE '%wpp%'
              AND tf.Tipo = 0
              AND NULLIF(TRIM(tf.Numero), '') IS NOT NULL
            LIMIT 1
        ),
        (
            SELECT NULLIF(tf.Numero, '')
            FROM telefonos tf
            WHERE tf.IDRef2 = c.IDContacto
              AND tf.Tipo = 0
              AND NULLIF(TRIM(tf.Numero), '') IS NOT NULL
            LIMIT 1
        ),
        (
            SELECT NULLIF(tf.Numero, '')
            FROM telefonos tf
            INNER JOIN contactos c2 ON c2.IDContacto = tf.IDRef2
            WHERE c2.IDEmpresa = e.IDEmpresa
              AND tf.Tipo = 0
              AND NULLIF(TRIM(tf.Numero), '') IS NOT NULL
            LIMIT 1
        ),
        (
            SELECT NULLIF(tf.Numero, '')
            FROM telefonos tf
            WHERE tf.IDRef2 = c.IDContacto
              AND NULLIF(TRIM(tf.Numero), '') IS NOT NULL
            ORDER BY tf.Defecto DESC
            LIMIT 1
        )
    ) AS telefono_cliente,
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
LEFT JOIN productosstocknroserie ns
    ON ns.RecID = s.IDNroSerie
WHERE e.Empresa != 'Mantenimiento Flota Porta'
  AND (
        -- "service 250 Hs", "servicio preventivo", "service250hs", etc.
        LOWER(COALESCE(s.Problema, '')) REGEXP 'servi(cio|ce)[[:space:]]*(preventivo|[0-9])'
        -- "serv. 250 Hs", "serv.250hs"
     OR LOWER(COALESCE(s.Problema, '')) REGEXP 'serv\\.[[:space:]]*[0-9]'
        -- "preventivo 250hs", "preventivo semestral"
     OR LOWER(COALESCE(s.Problema, '')) REGEXP 'preventivo[[:space:]]*(semestral|[0-9])'
        -- "250 hs service", "1000hs service" (numero antes de la palabra)
     OR LOWER(COALESCE(s.Problema, '')) REGEXP '[0-9]+[[:space:]]*hs[[:space:]]*(servi|prev)'
        -- "servicio/reparacion 250hs", "reparacion 250 hs", "serv/rep"
     OR LOWER(COALESCE(s.Problema, '')) REGEXP 'servi(cio|ce)[[:space:]]*/[[:space:]]*reparaci'
     OR LOWER(COALESCE(s.Problema, '')) REGEXP 'reparaci[oó]n[[:space:]]*[0-9]'
        -- "servicio de 500hs", "service de mantenimiento preventivo de 100hs"
     OR LOWER(COALESCE(s.Problema, '')) REGEXP 'servi(cio|ce)[[:space:]]+de[[:space:]]+[0-9]'
     OR LOWER(COALESCE(s.Problema, '')) REGEXP 'servi(cio|ce)[[:space:]]+de[[:space:]]+mantenimiento'
        -- "preventivo de 100hs", "preventivo de 250 hs"
     OR LOWER(COALESCE(s.Problema, '')) REGEXP 'preventivo[[:space:]]+de[[:space:]]*[0-9]'
        -- "servicio trimestral", "service trimestral"
     OR LOWER(COALESCE(s.Problema, '')) REGEXP 'servi(cio|ce)[[:space:]]*(de[[:space:]]+)?trimestral'
        -- "servicio semestral", "service semestral"
     OR LOWER(COALESCE(s.Problema, '')) REGEXP 'servi(cio|ce)[[:space:]]*(de[[:space:]]+)?semestral'
        -- "chequeo pre entrega", "consulta de hs" (lecturas iniciales de horimetro)
     OR LOWER(COALESCE(s.Problema, '')) REGEXP 'chequeo[[:space:]]+pre[[:space:]]+entrega'
     OR LOWER(COALESCE(s.Problema, '')) REGEXP 'consulta[[:space:]]+de[[:space:]]+hs'
        -- typos frecuentes: "Sevicio" (sin r), "Servico" (sin i), "Servicios" (plural)
     OR LOWER(COALESCE(s.Problema, '')) REGEXP 'sevi(cio|ce)[[:space:]]*(de[[:space:]]+)?(preventivo|[0-9])'
     OR LOWER(COALESCE(s.Problema, '')) REGEXP 'servico[[:space:]]*(de[[:space:]]+)?(preventivo|[0-9])'
     OR LOWER(COALESCE(s.Problema, '')) REGEXP 'servicios?[[:space:]]*(de[[:space:]]+)?[0-9]'
        -- "mantenimiento preventivo" sin numero explicito
     OR LOWER(COALESCE(s.Problema, '')) REGEXP 'mantenimiento[[:space:]]+(de[[:space:]]+)?preventivo'
      )
  AND COALESCE(s.Fecha, s.FechaCreacion) >= DATE_SUB(CURDATE(), INTERVAL 60 MONTH)
  AND ns.Numero IS NOT NULL
GROUP BY s.RecID
ORDER BY ns.Numero, CASE
    WHEN STR_TO_DATE(NULLIF(i.Campo2, ''), '%d/%m/%Y') IS NOT NULL
         AND YEAR(STR_TO_DATE(NULLIF(i.Campo2, ''), '%d/%m/%Y')) = YEAR(COALESCE(s.Fecha, s.FechaCreacion))
    THEN STR_TO_DATE(NULLIF(i.Campo2, ''), '%d/%m/%Y')
    ELSE COALESCE(s.Fecha, s.FechaCreacion)
END;
