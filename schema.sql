--
-- PostgreSQL database dump
--

\restrict WVtH31WeXGojyiEqepXKVdRRgSdi0COL0pOwAuUulj7Wr2NSLlb6IQd5ih3TKfM

-- Dumped from database version 17.10 (21f7c76)
-- Dumped by pg_dump version 17.10 (Ubuntu 17.10-1.pgdg24.04+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

-- *not* creating schema, since initdb creates it


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS '';


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: alert_kind; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.alert_kind AS ENUM (
    'Portfolio',
    'Asset',
    'Account',
    'Position'
);


--
-- Name: asset_kind; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.asset_kind AS ENUM (
    'stock',
    'etf',
    'fund',
    'crypto',
    'other'
);


--
-- Name: risk_profile_kind; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.risk_profile_kind AS ENUM (
    'moderate',
    'agressive',
    'conservative'
);


--
-- Name: transaction_kind; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.transaction_kind AS ENUM (
    'buy',
    'sell',
    'dividend',
    'fee',
    'deposit',
    'withdrawal'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: account_daily_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.account_daily_metrics (
    id uuid NOT NULL,
    account_id uuid NOT NULL,
    date date,
    pnl numeric(18,2),
    max_drawdown numeric(18,2),
    volatility numeric(8,6)
);


--
-- Name: account_monthly_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.account_monthly_metrics (
    id uuid NOT NULL,
    account_id uuid NOT NULL,
    date date,
    twr numeric(10,8),
    dietz numeric(10,8),
    sharpe_ratio numeric(6,4),
    var numeric(18,2),
    sortino numeric(6,4),
    assets_correlation numeric(5,4)
);


--
-- Name: accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounts (
    id uuid NOT NULL,
    user_id character varying NOT NULL,
    name character varying NOT NULL,
    broker character varying,
    currency character varying(3) DEFAULT 'USD'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: alerts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alerts (
    id uuid NOT NULL,
    user_id character varying NOT NULL,
    type character varying NOT NULL,
    trigger_field character varying DEFAULT ''::character varying NOT NULL,
    trigger_value numeric NOT NULL,
    threshold_value numeric NOT NULL,
    msg text NOT NULL,
    notified_at timestamp without time zone,
    last_triggered date,
    is_active boolean DEFAULT true NOT NULL,
    is_read boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: asset_daily_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.asset_daily_metrics (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    asset_id uuid NOT NULL,
    date date,
    absolute_return numeric(10,4),
    volatility numeric(10,4),
    max_drawdown numeric(10,4)
);


--
-- Name: asset_monthly_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.asset_monthly_metrics (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    asset_id uuid NOT NULL,
    date date,
    beta numeric(10,4)
);


--
-- Name: asset_prices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.asset_prices (
    asset_id uuid NOT NULL,
    date date NOT NULL,
    close numeric(20,8) NOT NULL,
    currency character varying(3) NOT NULL,
    source character varying
);


--
-- Name: assets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assets (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    symbol character varying NOT NULL,
    name character varying NOT NULL,
    kind public.asset_kind NOT NULL,
    currency character varying(3) DEFAULT 'USD'::character varying,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: dividends; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dividends (
    id uuid NOT NULL,
    account_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    date date NOT NULL,
    gross_amount numeric(18,2),
    tax_amount numeric(18,2),
    net_amount numeric(18,2)
);


--
-- Name: portfolio_daily_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.portfolio_daily_metrics (
    id uuid NOT NULL,
    date date,
    pnl numeric(18,2),
    max_drawdown numeric(18,2),
    volatility numeric(8,6),
    user_id character varying NOT NULL
);


--
-- Name: portfolio_monthly_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.portfolio_monthly_metrics (
    id uuid NOT NULL,
    date date,
    twr numeric(10,8),
    var numeric(18,2),
    user_id character varying NOT NULL
);


--
-- Name: portfolio_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.portfolio_snapshots (
    id uuid NOT NULL,
    user_id character varying NOT NULL,
    date date,
    total_value numeric(20,8),
    total_invested numeric(20,8),
    unrealized_pnl numeric(20,8),
    realized_pnl numeric(20,8),
    breakdown_by_currency jsonb,
    breakdown_by_account jsonb
);


--
-- Name: position_daily_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.position_daily_metrics (
    id uuid NOT NULL,
    position_id uuid NOT NULL,
    date date,
    unrealized_pnl numeric(20,8),
    total_pnl numeric(20,8)
);


--
-- Name: positions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.positions (
    id uuid NOT NULL,
    account_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    quantity numeric(20,8),
    avg_cost numeric(20,8),
    realized_pnl numeric(20,8),
    total_dividends numeric(20,8),
    total_fees numeric(20,8),
    last_transaction_at timestamp with time zone,
    updated_at timestamp with time zone
);


--
-- Name: profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.profiles (
    clerk_id character varying NOT NULL,
    email character varying,
    risk_profile public.risk_profile_kind,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transactions (
    id uuid NOT NULL,
    account_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    kind public.transaction_kind NOT NULL,
    quantity numeric(20,8) NOT NULL,
    price numeric(20,8),
    fee numeric(20,8) DEFAULT '0'::numeric NOT NULL,
    executed_at timestamp with time zone NOT NULL,
    date date,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_preferences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_preferences (
    id uuid NOT NULL,
    user_id character varying NOT NULL,
    pnl_percentage_account_daily numeric(5,4),
    pnl_percentage_asset_daily numeric(5,4),
    max_drawdown_portfolio_daily numeric(5,4),
    max_drawdown_account_daily numeric(5,4),
    asset_weight_weekly numeric(5,4),
    currency_exposure_weekly numeric(5,4)
);


--
-- Name: account_daily_metrics account_daily_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_daily_metrics
    ADD CONSTRAINT account_daily_metrics_pkey PRIMARY KEY (id);


--
-- Name: account_monthly_metrics account_monthly_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_monthly_metrics
    ADD CONSTRAINT account_monthly_metrics_pkey PRIMARY KEY (id);


--
-- Name: accounts accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: alerts alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_pkey PRIMARY KEY (id);


--
-- Name: asset_daily_metrics asset_daily_metrics_asset_id_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_daily_metrics
    ADD CONSTRAINT asset_daily_metrics_asset_id_date_key UNIQUE (asset_id, date);


--
-- Name: asset_daily_metrics asset_daily_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_daily_metrics
    ADD CONSTRAINT asset_daily_metrics_pkey PRIMARY KEY (id);


--
-- Name: asset_monthly_metrics asset_monthly_metrics_asset_id_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_monthly_metrics
    ADD CONSTRAINT asset_monthly_metrics_asset_id_date_key UNIQUE (asset_id, date);


--
-- Name: asset_monthly_metrics asset_monthly_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_monthly_metrics
    ADD CONSTRAINT asset_monthly_metrics_pkey PRIMARY KEY (id);


--
-- Name: asset_prices asset_prices_asset_id_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_prices
    ADD CONSTRAINT asset_prices_asset_id_date_key UNIQUE (asset_id, date);


--
-- Name: asset_prices asset_prices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_prices
    ADD CONSTRAINT asset_prices_pkey PRIMARY KEY (asset_id, date);


--
-- Name: assets assets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_pkey PRIMARY KEY (id);


--
-- Name: assets assets_symbol_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_symbol_name_key UNIQUE (symbol, name);


--
-- Name: dividends dividends_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dividends
    ADD CONSTRAINT dividends_pkey PRIMARY KEY (id);


--
-- Name: portfolio_daily_metrics portfolio_daily_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.portfolio_daily_metrics
    ADD CONSTRAINT portfolio_daily_metrics_pkey PRIMARY KEY (id);


--
-- Name: portfolio_monthly_metrics portfolio_monthly_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.portfolio_monthly_metrics
    ADD CONSTRAINT portfolio_monthly_metrics_pkey PRIMARY KEY (id);


--
-- Name: portfolio_snapshots portfolio_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.portfolio_snapshots
    ADD CONSTRAINT portfolio_snapshots_pkey PRIMARY KEY (id);


--
-- Name: position_daily_metrics position_daily_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.position_daily_metrics
    ADD CONSTRAINT position_daily_metrics_pkey PRIMARY KEY (id);


--
-- Name: positions positions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_pkey PRIMARY KEY (id);


--
-- Name: profiles profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_pkey PRIMARY KEY (clerk_id);


--
-- Name: transactions transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_pkey PRIMARY KEY (id);


--
-- Name: user_preferences user_preferences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_preferences
    ADD CONSTRAINT user_preferences_pkey PRIMARY KEY (id);


--
-- Name: ix_accounts_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_accounts_user_id ON public.accounts USING btree (user_id);


--
-- Name: ix_alerts_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_alerts_user_id ON public.alerts USING btree (user_id);


--
-- Name: ix_asset_price_asset_date_desc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_asset_price_asset_date_desc ON public.asset_prices USING btree (asset_id, date);


--
-- Name: ix_assets_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assets_symbol ON public.assets USING btree (symbol);


--
-- Name: ix_dividend_account_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_dividend_account_date ON public.dividends USING btree (account_id, date);


--
-- Name: ix_portfolio_snapshots_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_portfolio_snapshots_user_id ON public.portfolio_snapshots USING btree (user_id);


--
-- Name: ix_transaction_account_executed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transaction_account_executed ON public.transactions USING btree (account_id, executed_at);


--
-- Name: ix_user_preferences_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_preferences_user_id ON public.user_preferences USING btree (user_id);


--
-- Name: account_daily_metrics account_daily_metrics_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_daily_metrics
    ADD CONSTRAINT account_daily_metrics_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE;


--
-- Name: account_monthly_metrics account_monthly_metrics_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_monthly_metrics
    ADD CONSTRAINT account_monthly_metrics_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE;


--
-- Name: accounts accounts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(clerk_id);


--
-- Name: alerts alerts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alerts
    ADD CONSTRAINT alerts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(clerk_id);


--
-- Name: asset_daily_metrics asset_daily_metrics_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_daily_metrics
    ADD CONSTRAINT asset_daily_metrics_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;


--
-- Name: asset_monthly_metrics asset_monthly_metrics_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_monthly_metrics
    ADD CONSTRAINT asset_monthly_metrics_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;


--
-- Name: asset_prices asset_prices_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_prices
    ADD CONSTRAINT asset_prices_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;


--
-- Name: dividends dividends_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dividends
    ADD CONSTRAINT dividends_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE;


--
-- Name: dividends dividends_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dividends
    ADD CONSTRAINT dividends_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE RESTRICT;


--
-- Name: portfolio_daily_metrics pdm_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.portfolio_daily_metrics
    ADD CONSTRAINT pdm_user_id_fk FOREIGN KEY (user_id) REFERENCES public.profiles(clerk_id);


--
-- Name: portfolio_monthly_metrics pmm_user_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.portfolio_monthly_metrics
    ADD CONSTRAINT pmm_user_id_fk FOREIGN KEY (user_id) REFERENCES public.profiles(clerk_id);


--
-- Name: portfolio_snapshots portfolio_snapshots_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.portfolio_snapshots
    ADD CONSTRAINT portfolio_snapshots_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(clerk_id);


--
-- Name: position_daily_metrics position_daily_metrics_position_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.position_daily_metrics
    ADD CONSTRAINT position_daily_metrics_position_id_fkey FOREIGN KEY (position_id) REFERENCES public.positions(id) ON DELETE CASCADE;


--
-- Name: positions positions_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE;


--
-- Name: positions positions_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;


--
-- Name: transactions transactions_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE;


--
-- Name: transactions transactions_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE RESTRICT;


--
-- Name: user_preferences user_preferences_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_preferences
    ADD CONSTRAINT user_preferences_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(clerk_id);


--
-- PostgreSQL database dump complete
--

\unrestrict WVtH31WeXGojyiEqepXKVdRRgSdi0COL0pOwAuUulj7Wr2NSLlb6IQd5ih3TKfM

