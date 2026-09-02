--
-- PostgreSQL database dump
--

\restrict feclqkNdL1dhy8pnMuZlJP97zZWBscmWYvTMSa3CJvbjGOEotNEMQnxAkMUarwj

-- Dumped from database version 15.15
-- Dumped by pg_dump version 15.15

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: actualizar_timestamp(); Type: FUNCTION; Schema: public; Owner: notarial_user
--

CREATE FUNCTION public.actualizar_timestamp() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.actualizado_en = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.actualizar_timestamp() OWNER TO notarial_user;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: auditoria; Type: TABLE; Schema: public; Owner: notarial_user
--

CREATE TABLE public.auditoria (
    id integer NOT NULL,
    documento_id integer,
    usuario_id integer,
    accion character varying(50) NOT NULL,
    detalles jsonb,
    ip_address character varying(45),
    user_agent text,
    fecha timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.auditoria OWNER TO notarial_user;

--
-- Name: auditoria_id_seq; Type: SEQUENCE; Schema: public; Owner: notarial_user
--

CREATE SEQUENCE public.auditoria_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.auditoria_id_seq OWNER TO notarial_user;

--
-- Name: auditoria_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: notarial_user
--

ALTER SEQUENCE public.auditoria_id_seq OWNED BY public.auditoria.id;


--
-- Name: configuracion; Type: TABLE; Schema: public; Owner: notarial_user
--

CREATE TABLE public.configuracion (
    clave character varying(100) NOT NULL,
    valor text,
    descripcion text,
    actualizado_en timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.configuracion OWNER TO notarial_user;

--
-- Name: documentos; Type: TABLE; Schema: public; Owner: notarial_user
--

CREATE TABLE public.documentos (
    id integer NOT NULL,
    session_id character varying(100) NOT NULL,
    nombre_archivo character varying(255) NOT NULL,
    ruta_archivo character varying(500),
    fecha_procesamiento timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    usuario_id integer,
    estado character varying(20) DEFAULT 'procesado'::character varying,
    tiempo_procesamiento double precision,
    metodo_ocr character varying(50),
    numero_escritura character varying(50),
    fecha_escritura date,
    tipo_acto character varying(100),
    otorgantes text,
    identificaciones text,
    cuantia numeric(15,2),
    total_paginas integer,
    confianza_promedio double precision,
    requiere_revision boolean DEFAULT false,
    notas text,
    creado_en timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    actualizado_en timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.documentos OWNER TO notarial_user;

--
-- Name: documentos_id_seq; Type: SEQUENCE; Schema: public; Owner: notarial_user
--

CREATE SEQUENCE public.documentos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.documentos_id_seq OWNER TO notarial_user;

--
-- Name: documentos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: notarial_user
--

ALTER SEQUENCE public.documentos_id_seq OWNED BY public.documentos.id;


--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: notarial_user
--

CREATE TABLE public.usuarios (
    id integer NOT NULL,
    username character varying(50) NOT NULL,
    password_hash character varying(255) NOT NULL,
    nombre_completo character varying(100),
    rol character varying(20) DEFAULT 'usuario'::character varying,
    activo boolean DEFAULT true,
    fecha_creacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    ultimo_acceso timestamp without time zone
);


ALTER TABLE public.usuarios OWNER TO notarial_user;

--
-- Name: usuarios_id_seq; Type: SEQUENCE; Schema: public; Owner: notarial_user
--

CREATE SEQUENCE public.usuarios_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.usuarios_id_seq OWNER TO notarial_user;

--
-- Name: usuarios_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: notarial_user
--

ALTER SEQUENCE public.usuarios_id_seq OWNED BY public.usuarios.id;


--
-- Name: auditoria id; Type: DEFAULT; Schema: public; Owner: notarial_user
--

ALTER TABLE ONLY public.auditoria ALTER COLUMN id SET DEFAULT nextval('public.auditoria_id_seq'::regclass);


--
-- Name: documentos id; Type: DEFAULT; Schema: public; Owner: notarial_user
--

ALTER TABLE ONLY public.documentos ALTER COLUMN id SET DEFAULT nextval('public.documentos_id_seq'::regclass);


--
-- Name: usuarios id; Type: DEFAULT; Schema: public; Owner: notarial_user
--

ALTER TABLE ONLY public.usuarios ALTER COLUMN id SET DEFAULT nextval('public.usuarios_id_seq'::regclass);


--
-- Data for Name: auditoria; Type: TABLE DATA; Schema: public; Owner: notarial_user
--

COPY public.auditoria (id, documento_id, usuario_id, accion, detalles, ip_address, user_agent, fecha) FROM stdin;
1	\N	1	login	{"ip": "127.0.0.1"}	127.0.0.1	Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36	2026-02-03 21:54:01.715843
2	1	1	procesamiento	{"success": true, "codigos_faltantes": 0, "archivos_generados": 1, "codigos_encontrados": 1}	127.0.0.1	python-requests/2.31.0	2026-02-04 15:41:10.184956
3	2	1	procesamiento	{"success": true, "codigos_faltantes": 0, "archivos_generados": 1, "codigos_encontrados": 1}	127.0.0.1	python-requests/2.31.0	2026-02-04 16:00:57.326934
4	3	1	procesamiento	{"success": true, "codigos_faltantes": 0, "archivos_generados": 1, "codigos_encontrados": 1}	127.0.0.1	python-requests/2.31.0	2026-02-04 16:01:29.183831
5	4	1	procesamiento	{"success": true, "codigos_faltantes": 0, "archivos_generados": 1, "codigos_encontrados": 1}	127.0.0.1	python-requests/2.31.0	2026-02-04 16:09:11.879355
6	5	1	procesamiento	{"success": true, "codigos_faltantes": 0, "archivos_generados": 1, "codigos_encontrados": 1}	127.0.0.1	python-requests/2.31.0	2026-02-04 16:16:42.448315
7	6	1	procesamiento	{"success": true, "codigos_faltantes": 0, "archivos_generados": 4, "codigos_encontrados": 4}	127.0.0.1	python-requests/2.31.0	2026-02-04 17:57:56.788958
8	\N	1	login	{"ip": "127.0.0.1"}	127.0.0.1	Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36	2026-02-04 20:09:13.119597
9	\N	1	login	{"ip": "127.0.0.1"}	127.0.0.1	Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36	2026-02-04 22:05:26.880265
10	7	1	procesamiento	{"success": true, "codigos_faltantes": 0, "archivos_generados": 3, "codigos_encontrados": 3}	127.0.0.1	python-requests/2.31.0	2026-02-04 22:12:33.038962
11	8	1	procesamiento	{"success": true, "codigos_faltantes": 0, "archivos_generados": 4, "codigos_encontrados": 4}	127.0.0.1	python-requests/2.31.0	2026-02-04 22:38:44.908016
12	9	1	procesamiento	{"success": true, "codigos_faltantes": 0, "archivos_generados": 1, "codigos_encontrados": 1}	127.0.0.1	python-requests/2.31.0	2026-02-04 22:41:40.367349
13	10	1	procesamiento	{"success": true, "codigos_faltantes": 0, "archivos_generados": 1, "codigos_encontrados": 1}	127.0.0.1	python-requests/2.31.0	2026-02-04 22:43:40.410393
14	11	1	procesamiento	{"success": true, "codigos_faltantes": 0, "archivos_generados": 1, "codigos_encontrados": 1}	127.0.0.1	python-requests/2.31.0	2026-02-04 22:46:08.317648
15	12	1	procesamiento	{"success": true, "codigos_faltantes": 0, "archivos_generados": 1, "codigos_encontrados": 1}	127.0.0.1	python-requests/2.31.0	2026-02-05 00:55:31.65132
16	13	1	procesamiento	{"success": true, "codigos_faltantes": 0, "archivos_generados": 3, "codigos_encontrados": 3}	127.0.0.1	python-requests/2.31.0	2026-02-05 15:31:53.058616
17	14	1	procesamiento	{"success": true, "codigos_faltantes": 0, "archivos_generados": 3, "codigos_encontrados": 3}	127.0.0.1	python-requests/2.31.0	2026-02-05 15:46:00.409936
18	\N	1	login	{"ip": "127.0.0.1"}	127.0.0.1	Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36	2026-02-05 15:48:48.875727
19	15	1	procesamiento	{"success": true, "codigos_faltantes": 1, "archivos_generados": 66, "codigos_encontrados": 66}	127.0.0.1	Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36	2026-02-05 15:50:27.24784
20	\N	1	login	{"ip": "192.168.3.124"}	192.168.3.124	Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36	2026-02-05 18:19:18.220849
21	\N	1	login	{"ip": "192.168.3.124"}	192.168.3.124	Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36	2026-02-05 20:30:04.013898
\.


--
-- Data for Name: configuracion; Type: TABLE DATA; Schema: public; Owner: notarial_user
--

COPY public.configuracion (clave, valor, descripcion, actualizado_en) FROM stdin;
version_db	1.0	Versión del esquema de base de datos	2026-02-03 21:15:27.809048
ocr_method	hybrid	Método de OCR por defecto	2026-02-03 21:15:27.809048
max_file_size_mb	50	Tamaño máximo de archivo en MB	2026-02-03 21:15:27.809048
\.


--
-- Data for Name: documentos; Type: TABLE DATA; Schema: public; Owner: notarial_user
--

COPY public.documentos (id, session_id, nombre_archivo, ruta_archivo, fecha_procesamiento, usuario_id, estado, tiempo_procesamiento, metodo_ocr, numero_escritura, fecha_escritura, tipo_acto, otorgantes, identificaciones, cuantia, total_paginas, confianza_promedio, requiere_revision, notas, creado_en, actualizado_en) FROM stdin;
1	8be2f56a-3014-42df-8425-fbd5d397c469	scan_2025_D.pdf	2025/DILIGENCIA/	2026-02-04 15:41:10.180706	1	procesado	\N	hybrid	\N	\N	\N	\N	\N	\N	\N	\N	f	\N	2026-02-04 15:41:10.180708	2026-02-04 15:41:10.180709
2	b89d0e49-2e29-4612-9cfc-447555c04a70	scan_2025_D.pdf	2025/DILIGENCIA/	2026-02-04 16:00:57.323975	1	procesado	\N	hybrid	\N	\N	\N	\N	\N	\N	\N	\N	f	REPORTE_2025_D_20260204_110057.pdf	2026-02-04 16:00:57.323978	2026-02-04 16:00:57.323979
3	3cc0ea47-cea7-4bb5-a008-147943ce37b5	scan_2025_D.pdf	2025/DILIGENCIA/	2026-02-04 16:01:29.182681	1	procesado	\N	hybrid	\N	\N	\N	\N	\N	\N	\N	\N	f	REPORTE_2025_D_20260204_110129.pdf	2026-02-04 16:01:29.182684	2026-02-04 16:01:29.182685
4	20202440-5f6c-4960-aa56-1753c73e1f67	scan_2025_D.pdf	2025/DILIGENCIA/	2026-02-04 16:09:11.87214	1	procesado	\N	hybrid	\N	\N	\N	\N	\N	\N	\N	\N	f	REPORTE_2025_D_20260204_110911.pdf	2026-02-04 16:09:11.872144	2026-02-04 16:09:11.872145
5	05910914-8f0b-44fd-b797-227bfdfe8055	scan_2025_D.pdf	2025/DILIGENCIA/	2026-02-04 16:16:42.443945	1	procesado	\N	hybrid	\N	\N	\N	\N	\N	\N	\N	\N	f	REPORTE_2025_D_20260204_111642.pdf	2026-02-04 16:16:42.443947	2026-02-04 16:16:42.443948
6	ec3aab3d-67aa-4279-a950-fb025f10d4b4	scan_2025_D.pdf	2025/DILIGENCIA/	2026-02-04 17:57:56.784464	1	procesado	\N	hybrid	\N	\N	\N	\N	\N	\N	\N	\N	f	REPORTE_2025_D_20260204_125755.pdf	2026-02-04 17:57:56.784469	2026-02-04 17:57:56.78447
7	c4cfeb7e-c806-4229-89d0-9910ee90e2aa	scan_2025_D.pdf	2025/DILIGENCIA/	2026-02-04 22:12:33.032168	1	procesado	\N	hybrid	\N	\N	\N	\N	\N	\N	\N	\N	f	REPORTE_2025_D_20260204_171232.pdf	2026-02-04 22:12:33.032172	2026-02-04 22:12:33.032172
8	5a3f1ad0-218a-4374-884a-7e3ec0c3dad5	scan_2025_D.pdf	2025/DILIGENCIA/	2026-02-04 22:38:44.904248	1	procesado	\N	hybrid	\N	\N	\N	\N	\N	\N	\N	\N	f	REPORTE_2025_D_20260204_173844.pdf	2026-02-04 22:38:44.904253	2026-02-04 22:38:44.904255
9	2fdde08a-2e7d-4729-90c9-3726b10a7756	scan_2025_D.pdf	2025/DILIGENCIA/	2026-02-04 22:41:40.365029	1	procesado	\N	hybrid	\N	\N	\N	\N	\N	\N	\N	\N	f	REPORTE_2025_D_20260204_174140.pdf	2026-02-04 22:41:40.365034	2026-02-04 22:41:40.365035
10	e731e82e-374c-4e8a-bca4-cc2a818e5b17	scan_2025_D.pdf	2025/DILIGENCIA/	2026-02-04 22:43:40.408788	1	procesado	\N	hybrid	\N	\N	\N	\N	\N	\N	\N	\N	f	REPORTE_2025_D_20260204_174340.pdf	2026-02-04 22:43:40.408793	2026-02-04 22:43:40.408794
11	5868dc08-daef-4655-adec-04eb02e96670	scan_2025_D.pdf	2025/DILIGENCIA/	2026-02-04 22:46:08.312529	1	procesado	\N	hybrid	\N	\N	\N	\N	\N	\N	\N	\N	f	REPORTE_2025_D_20260204_174607.pdf	2026-02-04 22:46:08.312533	2026-02-04 22:46:08.312535
12	806b68c4-afc1-464e-9922-b69a922c03bd	scan_2024_P.pdf	2024/PROTOCOLO/	2026-02-05 00:55:31.647669	1	procesado	\N	hybrid	\N	\N	\N	\N	\N	\N	\N	\N	f	REPORTE_2024_P_20260204_195531.pdf	2026-02-05 00:55:31.647672	2026-02-05 00:55:31.647672
13	de324db1-c9fe-442f-8de1-fc0f62d551b1	scan_2025_D.pdf	2025/DILIGENCIA/	2026-02-05 15:31:53.052085	1	procesado	\N	hybrid	\N	\N	\N	\N	\N	\N	\N	\N	f	REPORTE_2025_D_20260205_103152.pdf	2026-02-05 15:31:53.052089	2026-02-05 15:31:53.052089
14	b944ec5f-9143-4009-a990-9331a481fe69	scan_2025_D.pdf	2025/DILIGENCIA/	2026-02-05 15:46:00.403081	1	procesado	\N	hybrid	\N	\N	\N	\N	\N	\N	\N	\N	f	REPORTE_2025_D_20260205_104559.pdf	2026-02-05 15:46:00.403085	2026-02-05 15:46:00.403086
15	7723993a-ab67-41c1-ab4e-cc58cc90343c	arriendos_enero-marzo_2025.pdf	2025/ARRIENDOS/	2026-02-05 15:50:27.246139	1	procesado	\N	hybrid	\N	\N	\N	\N	\N	\N	\N	\N	t	REPORTE_2025_A_20260205_105026.pdf	2026-02-05 15:50:27.246145	2026-02-05 15:50:27.246146
\.


--
-- Data for Name: usuarios; Type: TABLE DATA; Schema: public; Owner: notarial_user
--

COPY public.usuarios (id, username, password_hash, nombre_completo, rol, activo, fecha_creacion, ultimo_acceso) FROM stdin;
1	admin	pbkdf2:sha256:600000$FTHWvCOEHvw8flxr$fafb82f0fc49ce8322f54f154bf187dde0b4ed1a8a331530aa91856f5ccf434e	Administrador	admin	t	2026-02-03 21:15:27.807313	2026-02-05 20:30:03.998088
\.


--
-- Name: auditoria_id_seq; Type: SEQUENCE SET; Schema: public; Owner: notarial_user
--

SELECT pg_catalog.setval('public.auditoria_id_seq', 21, true);


--
-- Name: documentos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: notarial_user
--

SELECT pg_catalog.setval('public.documentos_id_seq', 15, true);


--
-- Name: usuarios_id_seq; Type: SEQUENCE SET; Schema: public; Owner: notarial_user
--

SELECT pg_catalog.setval('public.usuarios_id_seq', 1, true);


--
-- Name: auditoria auditoria_pkey; Type: CONSTRAINT; Schema: public; Owner: notarial_user
--

ALTER TABLE ONLY public.auditoria
    ADD CONSTRAINT auditoria_pkey PRIMARY KEY (id);


--
-- Name: configuracion configuracion_pkey; Type: CONSTRAINT; Schema: public; Owner: notarial_user
--

ALTER TABLE ONLY public.configuracion
    ADD CONSTRAINT configuracion_pkey PRIMARY KEY (clave);


--
-- Name: documentos documentos_pkey; Type: CONSTRAINT; Schema: public; Owner: notarial_user
--

ALTER TABLE ONLY public.documentos
    ADD CONSTRAINT documentos_pkey PRIMARY KEY (id);


--
-- Name: documentos documentos_session_id_key; Type: CONSTRAINT; Schema: public; Owner: notarial_user
--

ALTER TABLE ONLY public.documentos
    ADD CONSTRAINT documentos_session_id_key UNIQUE (session_id);


--
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: notarial_user
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id);


--
-- Name: usuarios usuarios_username_key; Type: CONSTRAINT; Schema: public; Owner: notarial_user
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_username_key UNIQUE (username);


--
-- Name: idx_auditoria_documento; Type: INDEX; Schema: public; Owner: notarial_user
--

CREATE INDEX idx_auditoria_documento ON public.auditoria USING btree (documento_id);


--
-- Name: idx_auditoria_fecha; Type: INDEX; Schema: public; Owner: notarial_user
--

CREATE INDEX idx_auditoria_fecha ON public.auditoria USING btree (fecha);


--
-- Name: idx_documentos_fecha; Type: INDEX; Schema: public; Owner: notarial_user
--

CREATE INDEX idx_documentos_fecha ON public.documentos USING btree (fecha_procesamiento);


--
-- Name: idx_documentos_numero; Type: INDEX; Schema: public; Owner: notarial_user
--

CREATE INDEX idx_documentos_numero ON public.documentos USING btree (numero_escritura);


--
-- Name: idx_documentos_session; Type: INDEX; Schema: public; Owner: notarial_user
--

CREATE INDEX idx_documentos_session ON public.documentos USING btree (session_id);


--
-- Name: documentos trigger_actualizar_documentos; Type: TRIGGER; Schema: public; Owner: notarial_user
--

CREATE TRIGGER trigger_actualizar_documentos BEFORE UPDATE ON public.documentos FOR EACH ROW EXECUTE FUNCTION public.actualizar_timestamp();


--
-- Name: auditoria auditoria_documento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: notarial_user
--

ALTER TABLE ONLY public.auditoria
    ADD CONSTRAINT auditoria_documento_id_fkey FOREIGN KEY (documento_id) REFERENCES public.documentos(id) ON DELETE CASCADE;


--
-- Name: auditoria auditoria_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: notarial_user
--

ALTER TABLE ONLY public.auditoria
    ADD CONSTRAINT auditoria_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: documentos documentos_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: notarial_user
--

ALTER TABLE ONLY public.documentos
    ADD CONSTRAINT documentos_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- PostgreSQL database dump complete
--

\unrestrict feclqkNdL1dhy8pnMuZlJP97zZWBscmWYvTMSa3CJvbjGOEotNEMQnxAkMUarwj

