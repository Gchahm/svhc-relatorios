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
    };
    form: {
        search_placeholder: string;
        select_period: string;
        select_placeholder: string;
        no_results: string;
        loading: string;
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
        },
        form: {
            search_placeholder: "Pesquisar por descrição...",
            select_period: "Selecione um período",
            select_placeholder: "Selecionar...",
            no_results: "Nenhum resultado encontrado",
            loading: "Carregando...",
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
        },
        form: {
            search_placeholder: "Search by description...",
            select_period: "Select a period",
            select_placeholder: "Select...",
            no_results: "No results found",
            loading: "Loading...",
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
