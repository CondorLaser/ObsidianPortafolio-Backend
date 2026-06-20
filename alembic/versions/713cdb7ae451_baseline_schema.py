"""baseline schema (squash) - 1:1 neon develop

Revision ID: 713cdb7ae451
Revises: 
Create Date: 2026-06-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '713cdb7ae451'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- extensions & enum types ---
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public")

    op.execute("""
        CREATE TYPE public.alert_kind AS ENUM (
            'Portfolio', 'Asset', 'Account', 'Position'
        )
    """)
    op.execute("""
        CREATE TYPE public.asset_kind AS ENUM (
            'stock', 'etf', 'fund', 'crypto', 'other'
        )
    """)
    op.execute("""
        CREATE TYPE public.risk_profile_kind AS ENUM (
            'moderate', 'agressive', 'conservative'
        )
    """)
    op.execute("""
        CREATE TYPE public.transaction_kind AS ENUM (
            'buy', 'sell', 'dividend', 'fee', 'deposit', 'withdrawal'
        )
    """)

    # --- tables ---
    op.execute("""
        CREATE TABLE public.account_daily_metrics (
            id uuid NOT NULL,
            account_id uuid NOT NULL,
            date date,
            pnl numeric(18,2),
            max_drawdown numeric(18,2),
            volatility numeric(8,6)
        )
    """)

    op.execute("""
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
        )
    """)

    op.execute("""
        CREATE TABLE public.accounts (
            id uuid NOT NULL,
            user_id character varying NOT NULL,
            name character varying NOT NULL,
            broker character varying,
            currency character varying(3) DEFAULT 'USD'::character varying NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL
        )
    """)

    op.execute("""
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
        )
    """)

    op.execute("""
        CREATE TABLE public.asset_daily_metrics (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            asset_id uuid NOT NULL,
            date date,
            absolute_return numeric(10,4),
            volatility numeric(10,4),
            max_drawdown numeric(10,4)
        )
    """)

    op.execute("""
        CREATE TABLE public.asset_monthly_metrics (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            asset_id uuid NOT NULL,
            date date,
            beta numeric(10,4)
        )
    """)

    op.execute("""
        CREATE TABLE public.asset_prices (
            asset_id uuid NOT NULL,
            date date NOT NULL,
            close numeric(20,8) NOT NULL,
            currency character varying(3) NOT NULL,
            source character varying
        )
    """)

    op.execute("""
        CREATE TABLE public.assets (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            symbol character varying NOT NULL,
            name character varying NOT NULL,
            kind public.asset_kind NOT NULL,
            currency character varying(3) DEFAULT 'USD'::character varying,
            created_at timestamp with time zone DEFAULT now() NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE public.dividends (
            id uuid NOT NULL,
            account_id uuid NOT NULL,
            asset_id uuid NOT NULL,
            date date NOT NULL,
            gross_amount numeric(18,2),
            tax_amount numeric(18,2),
            net_amount numeric(18,2)
        )
    """)

    op.execute("""
        CREATE TABLE public.portfolio_daily_metrics (
            id uuid NOT NULL,
            date date,
            pnl numeric(18,2),
            max_drawdown numeric(18,2),
            volatility numeric(8,6),
            user_id character varying NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE public.portfolio_monthly_metrics (
            id uuid NOT NULL,
            date date,
            twr numeric(10,8),
            var numeric(18,2),
            user_id character varying NOT NULL
        )
    """)

    op.execute("""
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
        )
    """)

    op.execute("""
        CREATE TABLE public.position_daily_metrics (
            id uuid NOT NULL,
            position_id uuid NOT NULL,
            date date,
            unrealized_pnl numeric(20,8),
            total_pnl numeric(20,8)
        )
    """)

    op.execute("""
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
        )
    """)

    op.execute("""
        CREATE TABLE public.profiles (
            clerk_id character varying NOT NULL,
            email character varying,
            risk_profile public.risk_profile_kind,
            created_at timestamp with time zone DEFAULT now() NOT NULL
        )
    """)

    op.execute("""
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
        )
    """)

    op.execute("""
        CREATE TABLE public.user_preferences (
            id uuid NOT NULL,
            user_id character varying NOT NULL,
            pnl_percentage_account_daily numeric(5,4),
            pnl_percentage_asset_daily numeric(5,4),
            max_drawdown_portfolio_daily numeric(5,4),
            max_drawdown_account_daily numeric(5,4),
            asset_weight_weekly numeric(5,4),
            currency_exposure_weekly numeric(5,4)
        )
    """)

    # --- primary keys & unique constraints ---
    op.execute("ALTER TABLE ONLY public.account_daily_metrics ADD CONSTRAINT account_daily_metrics_pkey PRIMARY KEY (id)")
    op.execute("ALTER TABLE ONLY public.account_monthly_metrics ADD CONSTRAINT account_monthly_metrics_pkey PRIMARY KEY (id)")
    op.execute("ALTER TABLE ONLY public.accounts ADD CONSTRAINT accounts_pkey PRIMARY KEY (id)")
    op.execute("ALTER TABLE ONLY public.alerts ADD CONSTRAINT alerts_pkey PRIMARY KEY (id)")
    op.execute("ALTER TABLE ONLY public.asset_daily_metrics ADD CONSTRAINT asset_daily_metrics_asset_id_date_key UNIQUE (asset_id, date)")
    op.execute("ALTER TABLE ONLY public.asset_daily_metrics ADD CONSTRAINT asset_daily_metrics_pkey PRIMARY KEY (id)")
    op.execute("ALTER TABLE ONLY public.asset_monthly_metrics ADD CONSTRAINT asset_monthly_metrics_asset_id_date_key UNIQUE (asset_id, date)")
    op.execute("ALTER TABLE ONLY public.asset_monthly_metrics ADD CONSTRAINT asset_monthly_metrics_pkey PRIMARY KEY (id)")
    op.execute("ALTER TABLE ONLY public.asset_prices ADD CONSTRAINT asset_prices_asset_id_date_key UNIQUE (asset_id, date)")
    op.execute("ALTER TABLE ONLY public.asset_prices ADD CONSTRAINT asset_prices_pkey PRIMARY KEY (asset_id, date)")
    op.execute("ALTER TABLE ONLY public.assets ADD CONSTRAINT assets_pkey PRIMARY KEY (id)")
    op.execute("ALTER TABLE ONLY public.assets ADD CONSTRAINT assets_symbol_name_key UNIQUE (symbol, name)")
    op.execute("ALTER TABLE ONLY public.dividends ADD CONSTRAINT dividends_pkey PRIMARY KEY (id)")
    op.execute("ALTER TABLE ONLY public.portfolio_daily_metrics ADD CONSTRAINT portfolio_daily_metrics_pkey PRIMARY KEY (id)")
    op.execute("ALTER TABLE ONLY public.portfolio_monthly_metrics ADD CONSTRAINT portfolio_monthly_metrics_pkey PRIMARY KEY (id)")
    op.execute("ALTER TABLE ONLY public.portfolio_snapshots ADD CONSTRAINT portfolio_snapshots_pkey PRIMARY KEY (id)")
    op.execute("ALTER TABLE ONLY public.position_daily_metrics ADD CONSTRAINT position_daily_metrics_pkey PRIMARY KEY (id)")
    op.execute("ALTER TABLE ONLY public.positions ADD CONSTRAINT positions_pkey PRIMARY KEY (id)")
    op.execute("ALTER TABLE ONLY public.profiles ADD CONSTRAINT profiles_pkey PRIMARY KEY (clerk_id)")
    op.execute("ALTER TABLE ONLY public.transactions ADD CONSTRAINT transactions_pkey PRIMARY KEY (id)")
    op.execute("ALTER TABLE ONLY public.user_preferences ADD CONSTRAINT user_preferences_pkey PRIMARY KEY (id)")

    # --- indexes ---
    op.execute("CREATE INDEX ix_accounts_user_id ON public.accounts USING btree (user_id)")
    op.execute("CREATE INDEX ix_alerts_user_id ON public.alerts USING btree (user_id)")
    op.execute("CREATE INDEX ix_asset_price_asset_date_desc ON public.asset_prices USING btree (asset_id, date)")
    op.execute("CREATE INDEX ix_assets_symbol ON public.assets USING btree (symbol)")
    op.execute("CREATE INDEX ix_dividend_account_date ON public.dividends USING btree (account_id, date)")
    op.execute("CREATE INDEX ix_portfolio_snapshots_user_id ON public.portfolio_snapshots USING btree (user_id)")
    op.execute("CREATE INDEX ix_transaction_account_executed ON public.transactions USING btree (account_id, executed_at)")
    op.execute("CREATE INDEX ix_user_preferences_user_id ON public.user_preferences USING btree (user_id)")

    # --- foreign keys ---
    op.execute("ALTER TABLE ONLY public.account_daily_metrics ADD CONSTRAINT account_daily_metrics_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE ONLY public.account_monthly_metrics ADD CONSTRAINT account_monthly_metrics_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE ONLY public.accounts ADD CONSTRAINT accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(clerk_id)")
    op.execute("ALTER TABLE ONLY public.alerts ADD CONSTRAINT alerts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(clerk_id)")
    op.execute("ALTER TABLE ONLY public.asset_daily_metrics ADD CONSTRAINT asset_daily_metrics_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE ONLY public.asset_monthly_metrics ADD CONSTRAINT asset_monthly_metrics_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE ONLY public.asset_prices ADD CONSTRAINT asset_prices_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE ONLY public.dividends ADD CONSTRAINT dividends_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE ONLY public.dividends ADD CONSTRAINT dividends_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE RESTRICT")
    op.execute("ALTER TABLE ONLY public.portfolio_daily_metrics ADD CONSTRAINT pdm_user_id_fk FOREIGN KEY (user_id) REFERENCES public.profiles(clerk_id)")
    op.execute("ALTER TABLE ONLY public.portfolio_monthly_metrics ADD CONSTRAINT pmm_user_id_fk FOREIGN KEY (user_id) REFERENCES public.profiles(clerk_id)")
    op.execute("ALTER TABLE ONLY public.portfolio_snapshots ADD CONSTRAINT portfolio_snapshots_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(clerk_id)")
    op.execute("ALTER TABLE ONLY public.position_daily_metrics ADD CONSTRAINT position_daily_metrics_position_id_fkey FOREIGN KEY (position_id) REFERENCES public.positions(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE ONLY public.positions ADD CONSTRAINT positions_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE ONLY public.positions ADD CONSTRAINT positions_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE ONLY public.transactions ADD CONSTRAINT transactions_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE ONLY public.transactions ADD CONSTRAINT transactions_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE RESTRICT")
    op.execute("ALTER TABLE ONLY public.user_preferences ADD CONSTRAINT user_preferences_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.profiles(clerk_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.user_preferences CASCADE")
    op.execute("DROP TABLE IF EXISTS public.transactions CASCADE")
    op.execute("DROP TABLE IF EXISTS public.profiles CASCADE")
    op.execute("DROP TABLE IF EXISTS public.positions CASCADE")
    op.execute("DROP TABLE IF EXISTS public.position_daily_metrics CASCADE")
    op.execute("DROP TABLE IF EXISTS public.portfolio_snapshots CASCADE")
    op.execute("DROP TABLE IF EXISTS public.portfolio_monthly_metrics CASCADE")
    op.execute("DROP TABLE IF EXISTS public.portfolio_daily_metrics CASCADE")
    op.execute("DROP TABLE IF EXISTS public.dividends CASCADE")
    op.execute("DROP TABLE IF EXISTS public.assets CASCADE")
    op.execute("DROP TABLE IF EXISTS public.asset_prices CASCADE")
    op.execute("DROP TABLE IF EXISTS public.asset_monthly_metrics CASCADE")
    op.execute("DROP TABLE IF EXISTS public.asset_daily_metrics CASCADE")
    op.execute("DROP TABLE IF EXISTS public.alerts CASCADE")
    op.execute("DROP TABLE IF EXISTS public.accounts CASCADE")
    op.execute("DROP TABLE IF EXISTS public.account_monthly_metrics CASCADE")
    op.execute("DROP TABLE IF EXISTS public.account_daily_metrics CASCADE")

    op.execute("DROP TYPE IF EXISTS public.transaction_kind")
    op.execute("DROP TYPE IF EXISTS public.risk_profile_kind")
    op.execute("DROP TYPE IF EXISTS public.asset_kind")
    op.execute("DROP TYPE IF EXISTS public.alert_kind")
