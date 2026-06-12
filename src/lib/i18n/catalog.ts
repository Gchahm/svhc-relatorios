/**
 * I18N Message Catalog
 * Typed, nested dictionary with pt-BR as canonical locale and en as optional fallback.
 * Missing en keys automatically fall back to pt-BR at runtime.
 */

export type SupportedLocale = "pt-BR" | "en";

/**
 * Define the complete catalog shape for type safety.
 * All keys in pt-BR must be present here.
 */
export type CatalogShape = {
    nav: {
        home: string;
        entries: string;
        documents: string;
        alerts: string;
        dashboard: string;
        settings: string;
        reports: string;
        summary: string;
        comparison: string;
        vendors: string;
        units: string;
        fines: string;
        runs: string;
    };
    app: {
        title: string;
    };
    access: {
        denied_title: string;
        denied_message: string;
    };
    button: {
        submit: string;
        cancel: string;
        save: string;
        delete: string;
        close: string;
        search: string;
        download: string;
        upload: string;
    };
    page: {
        entries_title: string;
        entries_description: string;
        documents_title: string;
        documents_description: string;
        alerts_title: string;
        alerts_description: string;
        reports_title: string;
        reports_description: string;
        fines_title: string;
        fines_description: string;
        comparison_title: string;
        comparison_description: string;
        summary_title: string;
        summary_description: string;
        runs_title: string;
        runs_description: string;
        units_title: string;
        units_description: string;
        vendors_title: string;
        vendors_description: string;
        document_analyses_title: string;
        document_analyses_description: string;
    };
    dialog: {
        attachment_detail_title: string;
        confirm_delete_title: string;
        confirm_delete_message: string;
        attachment_analysis_detail: string;
    };
    table: {
        period: string;
        date: string;
        amount: string;
        vendor: string;
        description: string;
        attachment: string;
        actions: string;
        status: string;
        type: string;
        category: string;
        subcategory: string;
        unit: string;
        doc: string;
        amt: string;
        vnd: string;
        dt: string;
        title: string;
        severity: string;
        entries: string;
        number: string;
        issuer: string;
        total: string;
        sum_entries: string;
        links: string;
        revenue: string;
        expenses: string;
        month_balance: string;
        accumulated_balance: string;
        reason: string;
        block: string;
        share: string;
        run: string;
        executed_at: string;
        periods_scraped: string;
        attachments: string;
        errors: string;
        name: string;
        count: string;
        difference: string;
        pct_change: string;
        subcategories: string;
        period_base: string;
        period_compare: string;
        movement: string;
        duration_s: string;
        code: string;
        total_paid: string;
        vendor_name: string;
        pct_of_total: string;
    };
    runs: {
        status_success: string;
        status_error: string;
        status_running: string;
        missing_title: string;
        missing_message: string;
    };
    form: {
        search_placeholder: string;
        select_period: string;
        select_placeholder: string;
        no_results: string;
        loading: string;
        all: string;
        all_types: string;
        search_doc_placeholder: string;
        search_number_issuer: string;
        no_alerts: string;
        no_documents: string;
        no_entries: string;
        no_fines: string;
        no_vendors: string;
        no_units: string;
        no_runs: string;
        all_periods: string;
    };
    filter: {
        period: string;
        search: string;
        document_type: string;
        attachment_status: string;
        severity: string;
        type: string;
        status: string;
        block: string;
        reason: string;
        category: string;
        subcategory: string;
        categories_subcategories: string;
        periods: string;
    };
    status: {
        over: string;
        within: string;
        under: string;
        unknown: string;
    };
    severity: {
        critical: string;
        warning: string;
        info: string;
    };
    alert_status: {
        active: string;
        resolved: string;
    };
    match: {
        all_match: string;
        has_mismatch: string;
        has_error: string;
        amount: string;
        vendor: string;
        date: string;
        errors: string;
        docs: string;
    };
    count: {
        entries_one: string;
        entries_other: string;
        alerts_one: string;
        alerts_other: string;
        documents_one: string;
        documents_other: string;
        fines_one: string;
        fines_other: string;
        periods_one: string;
        periods_other: string;
        units_one: string;
        units_other: string;
        vendors_one: string;
        vendors_other: string;
        runs_one: string;
        runs_other: string;
        subcategories_one: string;
        subcategories_other: string;
        rows_one: string;
        rows_other: string;
    };
    summary: {
        revenue: string;
        expenses: string;
        net: string;
        total: string;
    };
    action: {
        open: string;
        dismiss: string;
    };
    notice: {
        deeplink_invalid: string;
        deeplink_not_found_prefix: string;
        deeplink_not_found_suffix: string;
    };
    meta: {
        total_value: string;
        sum_entries: string;
        over_amount: string;
        total: string;
        vendor_total: string;
        total_expenses: string;
        ledger_value: string;
        extracted_value: string;
        pct: string;
        rate_pct: string;
        count: string;
        paying: string;
        delinquent: string;
        kind: string;
        vendor_name: string;
        vendor_id: string;
        document_number: string;
        issuer_cnpj: string;
        date: string;
        description: string;
        movement_type: string;
    };
    badge: {
        pending: string;
        classified: string;
        analyzed: string;
        error: string;
        success: string;
        warning: string;
        info: string;
    };
    alert: {
        types: {
            attachment_amount_mismatch: string;
            attachment_vendor_mismatch: string;
            attachment_date_mismatch: string;
            attachment_page_error: string;
            duplicate_billing: string;
            duplicate_entry: string;
            negative_credit: string;
            large_expense_no_attachment: string;
            document_overpayment: string;
            scrape_inconsistency: string;
            portal_row_vanished: string;
        };
    };
    error: {
        not_found: string;
        unauthorized: string;
        server_error: string;
        network_error: string;
        loading_failed: string;
        generic_prefix: string;
    };
    list: {
        open_attachment_detail: string;
        open_alert_detail: string;
        open_document_detail: string;
        entry_n: string;
        documents_subtitle: string;
        doc_fallback: string;
    };
    common: {
        loading: string;
        no_data: string;
        error: string;
        success: string;
        confirm: string;
        yes: string;
        no: string;
    };
    auth: {
        sign_in_title: string;
        sign_in_description: string;
        email_label: string;
        password_label: string;
        sign_in_button: string;
        sign_in_error: string;
        invalid_credentials: string;
        session_expired: string;
        sign_out: string;
        sign_in_email_placeholder: string;
        signing_in: string;
        unexpected_error: string;
        no_account_prompt: string;
        create_account_link: string;
        sign_up_title: string;
        sign_up_description: string;
        name_label: string;
        name_placeholder: string;
        confirm_password_label: string;
        sign_up_button: string;
        signing_up: string;
        sign_up_error: string;
        email_in_use: string;
        passwords_no_match: string;
        have_account_prompt: string;
        sign_in_link: string;
        signing_out: string;
        sign_out_error: string;
    };
    formatting: {
        currency: string;
        date: string;
        percent: string;
    };
};

/**
 * Complete message catalog
 * pt-BR: canonical, complete translations
 * en: optional, partial translations (fallback to pt-BR)
 */
export const catalog: Record<SupportedLocale, CatalogShape> = {
    "pt-BR": {
        nav: {
            home: "Início",
            entries: "Lançamentos",
            documents: "Documentos",
            alerts: "Alertas",
            dashboard: "Dashboard",
            settings: "Configurações",
            reports: "Prestação de contas",
            summary: "Resumo",
            comparison: "Comparação",
            vendors: "Fornecedores",
            units: "Unidades",
            fines: "Multas",
            runs: "Execuções",
        },
        app: {
            title: "SVHC Fiscal",
        },
        access: {
            denied_title: "Acesso negado",
            denied_message:
                "Sua conta está aguardando aprovação. Entre em contato com um administrador para obter acesso.",
        },
        button: {
            submit: "Enviar",
            cancel: "Cancelar",
            save: "Salvar",
            delete: "Deletar",
            close: "Fechar",
            search: "Pesquisar",
            download: "Baixar",
            upload: "Enviar",
        },
        page: {
            entries_title: "Lançamentos",
            entries_description: "Visualize e analise os lançamentos do condomínio",
            documents_title: "Documentos",
            documents_description: "Documentos fiscais identificados e analisados",
            alerts_title: "Alertas",
            alerts_description: "Divergências e achados da auditoria",
            reports_title: "Prestações de Contas",
            reports_description: "Demonstrativos financeiros por período",
            fines_title: "Multas",
            fines_description: "Multas aplicadas às unidades do condomínio",
            comparison_title: "Comparação",
            comparison_description: "Compare os valores entre dois períodos",
            summary_title: "Resumo",
            summary_description: "Resumo financeiro por subcategoria",
            runs_title: "Execuções",
            runs_description: "Histórico das execuções de coleta",
            units_title: "Unidades",
            units_description: "Lançamentos agrupados por unidade",
            vendors_title: "Fornecedores",
            vendors_description: "Gastos agrupados por fornecedor",
            document_analyses_title: "Análises de Documentos",
            document_analyses_description: "Análises de classificação dos documentos",
        },
        dialog: {
            attachment_detail_title: "Detalhes do Documento",
            confirm_delete_title: "Confirmar Exclusão",
            confirm_delete_message: "Tem certeza que deseja excluir este item?",
            attachment_analysis_detail: "Análise do Documento",
        },
        table: {
            period: "Período",
            date: "Data",
            amount: "Valor",
            vendor: "Fornecedor",
            description: "Descrição",
            attachment: "Documento",
            actions: "Ações",
            status: "Status",
            type: "Tipo",
            category: "Categoria",
            subcategory: "Subcategoria",
            unit: "Unidade",
            doc: "Doc",
            amt: "Vlr",
            vnd: "Forn",
            dt: "Dt",
            title: "Título",
            severity: "Severidade",
            entries: "Lançamentos",
            number: "Número",
            issuer: "Emitente",
            total: "Total",
            sum_entries: "Soma lançamentos",
            links: "Vínculos",
            revenue: "Receitas",
            expenses: "Despesas",
            month_balance: "Saldo do mês",
            accumulated_balance: "Saldo acumulado",
            reason: "Motivo",
            block: "Bloco",
            share: "Participação",
            run: "Execução",
            executed_at: "Executado em",
            periods_scraped: "Períodos coletados",
            attachments: "Documentos",
            errors: "Erros",
            name: "Nome",
            count: "Quantidade",
            difference: "Diferença",
            pct_change: "% Var.",
            subcategories: "Subcategorias",
            period_base: "Período 1 (base)",
            period_compare: "Período 2",
            movement: "Tipo",
            duration_s: "Duração (s)",
            code: "Código",
            total_paid: "Total pago",
            vendor_name: "Fornecedor",
            pct_of_total: "% do Total",
        },
        runs: {
            status_success: "sucesso",
            status_error: "erro",
            status_running: "em execução",
            missing_title: "Períodos Faltando",
            missing_message: "Os seguintes períodos não possuem prestações de contas:",
        },
        form: {
            search_placeholder: "Pesquisar por descrição...",
            select_period: "Selecione um período",
            select_placeholder: "Selecionar...",
            no_results: "Nenhum resultado encontrado",
            loading: "Carregando...",
            all: "Todos",
            all_types: "Todos os tipos",
            search_doc_placeholder: "Número da NF ou emitente…",
            search_number_issuer: "Buscar (número / emitente)",
            no_alerts: "Nenhum alerta encontrado.",
            no_documents: "Nenhum documento encontrado.",
            no_entries: "Nenhum lançamento encontrado.",
            no_fines: "Nenhuma multa encontrada.",
            no_vendors: "Nenhum fornecedor encontrado.",
            no_units: "Nenhuma unidade encontrada.",
            no_runs: "Nenhuma execução encontrada.",
            all_periods: "Todos os períodos",
        },
        filter: {
            period: "Período",
            search: "Pesquisar",
            document_type: "Tipo de documento",
            attachment_status: "Status do documento",
            severity: "Severidade",
            type: "Tipo",
            status: "Status",
            block: "Bloco",
            reason: "Motivo",
            category: "Categoria",
            subcategory: "Subcategoria",
            categories_subcategories: "Categorias / Subcategorias",
            periods: "Períodos",
        },
        status: {
            over: "Acima",
            within: "Conforme",
            under: "Abaixo",
            unknown: "Desconhecido",
        },
        severity: {
            critical: "Crítico",
            warning: "Aviso",
            info: "Informação",
        },
        alert_status: {
            active: "Ativo",
            resolved: "Resolvido",
        },
        match: {
            all_match: "Todos conferem",
            has_mismatch: "Com divergência",
            has_error: "Com erro",
            amount: "valor",
            vendor: "fornecedor",
            date: "data",
            errors: "erros",
            docs: "docs",
        },
        count: {
            entries_one: "lançamento",
            entries_other: "lançamentos",
            alerts_one: "alerta",
            alerts_other: "alertas",
            documents_one: "documento",
            documents_other: "documentos",
            fines_one: "multa",
            fines_other: "multas",
            periods_one: "período",
            periods_other: "períodos",
            units_one: "unidade",
            units_other: "unidades",
            vendors_one: "fornecedor",
            vendors_other: "fornecedores",
            runs_one: "execução",
            runs_other: "execuções",
            subcategories_one: "subcategoria",
            subcategories_other: "subcategorias",
            rows_one: "linha",
            rows_other: "linhas",
        },
        summary: {
            revenue: "Receita",
            expenses: "Despesa",
            net: "Saldo",
            total: "Total",
        },
        action: {
            open: "Abrir",
            dismiss: "Dispensar",
        },
        notice: {
            deeplink_invalid: "A referência ao lançamento era inválida, então não foi possível abri-lo.",
            deeplink_not_found_prefix: "Lançamento",
            deeplink_not_found_suffix:
                "não encontrado — ele pode ter sido removido ou recoletado, ou o período pode estar incorreto.",
        },
        meta: {
            total_value: "Total do documento",
            sum_entries: "Soma dos lançamentos",
            over_amount: "Valor excedente",
            total: "Total",
            vendor_total: "Total do fornecedor",
            total_expenses: "Total de despesas",
            ledger_value: "Valor no livro",
            extracted_value: "Valor extraído",
            pct: "Participação",
            rate_pct: "Taxa",
            count: "Contagem",
            paying: "Pagantes",
            delinquent: "Inadimplentes",
            kind: "Tipo",
            vendor_name: "Fornecedor",
            vendor_id: "ID do fornecedor",
            document_number: "Nº do documento",
            issuer_cnpj: "CNPJ do emitente",
            date: "Data",
            description: "Descrição",
            movement_type: "Movimento",
        },
        badge: {
            pending: "Pendente",
            classified: "Classificado",
            analyzed: "Analisado",
            error: "Erro",
            success: "Sucesso",
            warning: "Aviso",
            info: "Informação",
        },
        alert: {
            types: {
                attachment_amount_mismatch: "Divergência de Valor",
                attachment_vendor_mismatch: "Divergência de Fornecedor",
                attachment_date_mismatch: "Divergência de Data",
                attachment_page_error: "Erro na Página",
                duplicate_billing: "Cobrança Duplicada",
                duplicate_entry: "Lançamento Duplicado",
                negative_credit: "Crédito Negativo",
                large_expense_no_attachment: "Grande Despesa sem Documento",
                document_overpayment: "Pagamento Excessivo do Documento",
                scrape_inconsistency: "Inconsistência nos Dados",
                portal_row_vanished: "Linha Removida do Portal",
            },
        },
        error: {
            not_found: "Não encontrado",
            unauthorized: "Não autorizado",
            server_error: "Erro no servidor",
            network_error: "Erro de conexão",
            loading_failed: "Falha ao carregar",
            generic_prefix: "Erro",
        },
        list: {
            open_attachment_detail: "Clique para ver o documento",
            open_alert_detail: "Clique para abrir o alerta",
            open_document_detail: "Clique para abrir o documento",
            entry_n: "Lançamento",
            documents_subtitle: "Notas Fiscais",
            doc_fallback: "doc",
        },
        common: {
            loading: "Carregando...",
            no_data: "Sem dados",
            error: "Erro",
            success: "Sucesso",
            confirm: "Confirmar",
            yes: "Sim",
            no: "Não",
        },
        auth: {
            sign_in_title: "Entrar",
            sign_in_description: "Acesse sua conta para continuar",
            email_label: "Email",
            password_label: "Senha",
            sign_in_button: "Entrar",
            sign_in_error: "Falha ao entrar.",
            invalid_credentials: "Email ou senha inválidos",
            session_expired: "Sua sessão expirou",
            sign_out: "Sair",
            sign_in_email_placeholder: "seu@email.com",
            signing_in: "Entrando...",
            unexpected_error: "Erro inesperado. Tente novamente.",
            no_account_prompt: "Não tem conta?",
            create_account_link: "Criar conta",
            sign_up_title: "Criar conta",
            sign_up_description: "Preencha os dados abaixo para se registrar.",
            name_label: "Nome",
            name_placeholder: "Seu nome",
            confirm_password_label: "Confirmar senha",
            sign_up_button: "Criar conta",
            signing_up: "Criando conta...",
            sign_up_error: "Falha ao criar conta.",
            email_in_use: "Este email já está em uso. Use outro email.",
            passwords_no_match: "As senhas não coincidem.",
            have_account_prompt: "Já tem conta?",
            sign_in_link: "Entrar",
            signing_out: "Saindo...",
            sign_out_error: "Falha ao sair. Tente novamente.",
        },
        formatting: {
            currency: "R$",
            date: "DD/MM/YYYY",
            percent: "%",
        },
    },
    en: {
        nav: {
            home: "Home",
            entries: "Entries",
            documents: "Documents",
            alerts: "Alerts",
            dashboard: "Dashboard",
            settings: "Settings",
            reports: "Reports",
            summary: "Summary",
            comparison: "Comparison",
            vendors: "Vendors",
            units: "Units",
            fines: "Fines",
            runs: "Runs",
        },
        app: {
            title: "SVHC Fiscal",
        },
        access: {
            denied_title: "Access Denied",
            denied_message: "Your account is pending approval. Contact an administrator to get access.",
        },
        button: {
            submit: "Submit",
            cancel: "Cancel",
            save: "Save",
            delete: "Delete",
            close: "Close",
            search: "Search",
            download: "Download",
            upload: "Upload",
        },
        page: {
            entries_title: "Entries",
            entries_description: "View and analyze condominium entries",
            documents_title: "Documents",
            documents_description: "Identified and analyzed fiscal documents",
            alerts_title: "Alerts",
            alerts_description: "Audit findings and discrepancies",
            reports_title: "Reports",
            reports_description: "Financial statements by period",
            fines_title: "Fines",
            fines_description: "Fines applied to condominium units",
            comparison_title: "Comparison",
            comparison_description: "Compare values between two periods",
            summary_title: "Summary",
            summary_description: "Financial summary by subcategory",
            runs_title: "Runs",
            runs_description: "Scrape run history",
            units_title: "Units",
            units_description: "Entries grouped by unit",
            vendors_title: "Vendors",
            vendors_description: "Spending grouped by vendor",
            document_analyses_title: "Document Analyses",
            document_analyses_description: "Document classification analyses",
        },
        dialog: {
            attachment_detail_title: "Document Details",
            confirm_delete_title: "Confirm Deletion",
            confirm_delete_message: "Are you sure you want to delete this item?",
            attachment_analysis_detail: "Document Analysis",
        },
        table: {
            period: "Period",
            date: "Date",
            amount: "Amount",
            vendor: "Vendor",
            description: "Description",
            attachment: "Document",
            actions: "Actions",
            status: "Status",
            type: "Type",
            category: "Category",
            subcategory: "Subcategory",
            unit: "Unit",
            doc: "Doc",
            amt: "Amt",
            vnd: "Vnd",
            dt: "Dt",
            title: "Title",
            severity: "Severity",
            entries: "Entries",
            number: "Number",
            issuer: "Issuer",
            total: "Total",
            sum_entries: "Sum entries",
            links: "Links",
            revenue: "Revenue",
            expenses: "Expenses",
            month_balance: "Month balance",
            accumulated_balance: "Accumulated balance",
            reason: "Reason",
            block: "Block",
            share: "Share",
            run: "Run",
            executed_at: "Executed at",
            periods_scraped: "Periods scraped",
            attachments: "Documents",
            errors: "Errors",
            name: "Name",
            count: "Count",
            difference: "Difference",
            pct_change: "% Chg.",
            subcategories: "Subcategories",
            period_base: "Period 1 (base)",
            period_compare: "Period 2",
            movement: "Type",
            duration_s: "Duration (s)",
            code: "Code",
            total_paid: "Total paid",
            vendor_name: "Vendor Name",
            pct_of_total: "% of Total",
        },
        runs: {
            status_success: "success",
            status_error: "error",
            status_running: "running",
            missing_title: "Missing Periods",
            missing_message: "The following periods have no accountability reports:",
        },
        form: {
            search_placeholder: "Search by description...",
            select_period: "Select a period",
            select_placeholder: "Select...",
            no_results: "No results found",
            loading: "Loading...",
            all: "All",
            all_types: "All types",
            search_doc_placeholder: "NF number or issuer…",
            search_number_issuer: "Search (number / issuer)",
            no_alerts: "No alerts found.",
            no_documents: "No documents found.",
            no_entries: "No entries found.",
            no_fines: "No fines found.",
            no_vendors: "No vendors found.",
            no_units: "No units found.",
            no_runs: "No runs found.",
            all_periods: "All periods",
        },
        filter: {
            period: "Period",
            search: "Search",
            document_type: "Document type",
            attachment_status: "Attachment status",
            severity: "Severity",
            type: "Type",
            status: "Status",
            block: "Block",
            reason: "Reason",
            category: "Category",
            subcategory: "Subcategory",
            categories_subcategories: "Categories / Subcategories",
            periods: "Periods",
        },
        status: {
            over: "Over",
            within: "Within",
            under: "Under",
            unknown: "Unknown",
        },
        severity: {
            critical: "Critical",
            warning: "Warning",
            info: "Info",
        },
        alert_status: {
            active: "Active",
            resolved: "Resolved",
        },
        match: {
            all_match: "All match",
            has_mismatch: "Has mismatch",
            has_error: "Has error",
            amount: "amount",
            vendor: "vendor",
            date: "date",
            errors: "errors",
            docs: "docs",
        },
        count: {
            entries_one: "entry",
            entries_other: "entries",
            alerts_one: "alert",
            alerts_other: "alerts",
            documents_one: "document",
            documents_other: "documents",
            fines_one: "fine",
            fines_other: "fines",
            periods_one: "period",
            periods_other: "periods",
            units_one: "unit",
            units_other: "units",
            vendors_one: "vendor",
            vendors_other: "vendors",
            runs_one: "run",
            runs_other: "runs",
            subcategories_one: "subcategory",
            subcategories_other: "subcategories",
            rows_one: "row",
            rows_other: "rows",
        },
        summary: {
            revenue: "Revenue",
            expenses: "Expenses",
            net: "Net",
            total: "Total",
        },
        action: {
            open: "Open",
            dismiss: "Dismiss",
        },
        notice: {
            deeplink_invalid: "The linked entry reference was invalid, so it could not be opened.",
            deeplink_not_found_prefix: "Entry",
            deeplink_not_found_suffix:
                "not found — it may have been removed or re-scraped, or the period may be wrong.",
        },
        meta: {
            total_value: "Document total",
            sum_entries: "Sum of entries",
            over_amount: "Over amount",
            total: "Total",
            vendor_total: "Vendor total",
            total_expenses: "Total expenses",
            ledger_value: "Ledger value",
            extracted_value: "Extracted value",
            pct: "Share",
            rate_pct: "Rate",
            count: "Count",
            paying: "Paying",
            delinquent: "Delinquent",
            kind: "Kind",
            vendor_name: "Vendor",
            vendor_id: "Vendor id",
            document_number: "Document №",
            issuer_cnpj: "Issuer CNPJ",
            date: "Date",
            description: "Description",
            movement_type: "Movement",
        },
        badge: {
            pending: "Pending",
            classified: "Classified",
            analyzed: "Analyzed",
            error: "Error",
            success: "Success",
            warning: "Warning",
            info: "Info",
        },
        alert: {
            types: {
                attachment_amount_mismatch: "Amount Mismatch",
                attachment_vendor_mismatch: "Vendor Mismatch",
                attachment_date_mismatch: "Date Mismatch",
                attachment_page_error: "Page Error",
                duplicate_billing: "Duplicate Billing",
                duplicate_entry: "Duplicate Entry",
                negative_credit: "Negative Credit",
                large_expense_no_attachment: "Large Expense No Attachment",
                document_overpayment: "Document Overpayment",
                scrape_inconsistency: "Data Inconsistency",
                portal_row_vanished: "Row Removed from Portal",
            },
        },
        error: {
            not_found: "Not found",
            unauthorized: "Unauthorized",
            server_error: "Server error",
            network_error: "Network error",
            loading_failed: "Failed to load",
            generic_prefix: "Error",
        },
        list: {
            open_attachment_detail: "Click for attachment detail",
            open_alert_detail: "Click to open the alert detail page",
            open_document_detail: "Click to open the document detail page",
            entry_n: "Entry",
            documents_subtitle: "Notas Fiscais",
            doc_fallback: "doc",
        },
        common: {
            loading: "Loading...",
            no_data: "No data",
            error: "Error",
            success: "Success",
            confirm: "Confirm",
            yes: "Yes",
            no: "No",
        },
        auth: {
            sign_in_title: "Sign In",
            sign_in_description: "Sign in to your account to continue",
            email_label: "Email",
            password_label: "Password",
            sign_in_button: "Sign In",
            sign_in_error: "Failed to sign in.",
            invalid_credentials: "Invalid email or password",
            session_expired: "Your session has expired",
            sign_out: "Sign Out",
            sign_in_email_placeholder: "you@email.com",
            signing_in: "Signing in...",
            unexpected_error: "Unexpected error. Please try again.",
            no_account_prompt: "Don't have an account?",
            create_account_link: "Create account",
            sign_up_title: "Create account",
            sign_up_description: "Fill in the details below to register.",
            name_label: "Name",
            name_placeholder: "Your name",
            confirm_password_label: "Confirm password",
            sign_up_button: "Create account",
            signing_up: "Creating account...",
            sign_up_error: "Failed to create account.",
            email_in_use: "This email is already in use. Use another email.",
            passwords_no_match: "Passwords do not match.",
            have_account_prompt: "Already have an account?",
            sign_in_link: "Sign in",
            signing_out: "Signing out...",
            sign_out_error: "Sign out failed. Please try again.",
        },
        formatting: {
            currency: "USD",
            date: "MM/DD/YYYY",
            percent: "%",
        },
    },
};

/**
 * Type helper for catalog keys (enables type-safe key lookup)
 */
export type CatalogKey = keyof CatalogShape;

/**
 * Recursively extract all dot-notation leaf paths from a nested catalog shape,
 * including nested sections like `alert.types.*` (so every key is type-checked).
 */
type Paths<T> = {
    [K in keyof T & string]: T[K] extends string ? K : `${K}.${Paths<T[K]>}`;
}[keyof T & string];

/**
 * Extract all possible keys from the catalog shape recursively
 */
export type DeepCatalogKey = Paths<CatalogShape>;
