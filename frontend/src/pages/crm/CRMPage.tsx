import { useEffect, useMemo, useState, type FormEvent } from 'react';
import {
  Search,
  Users,
  UserRound,
  Phone,
  Mail,
  CalendarDays,
  X,
  ChevronRight,
  RefreshCw,
  FileText,
  ShoppingBag,
  MessageCircle,
  AlertCircle,
  History,
  Loader2,
  Plus,
  Save,
} from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';

interface EstadoCliente {
  id: number;
  client_id?: number;
  tipo: string;
  status: string;
  descricao: string | null;
  forma_pagamento: string | null;
  valor_unitario: number | null;
  quantidade: number | null;
  valor_total: number | null;
  quant_quitada: number | null;
  data_vencimento: string | null;
  estado_anterior: number | null;
  created_at: string;
}

interface Cliente {
  id: number;
  nome: string;
  email: string | null;
  telefone: string | null;
  status: boolean;
  created_at: string;
  estados: EstadoCliente[];
}

const formatarData = (data?: string | null) => {
  if (!data) return 'Não informado';

  const parsed = new Date(data);

  if (Number.isNaN(parsed.getTime())) return 'Não informado';

  return parsed.toLocaleDateString('pt-BR');
};

const formatarDataHora = (data?: string | null) => {
  if (!data) return 'Não informado';

  const parsed = new Date(data);

  if (Number.isNaN(parsed.getTime())) return 'Não informado';

  return parsed.toLocaleString('pt-BR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const formatarMoeda = (valor?: number | null) => {
  if (valor === null || valor === undefined) return null;

  return Number(valor).toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  });
};

const nomeTipoEstado = (tipo: string) => {
  const nomes: Record<string, string> = {
    CONTATO: 'Contato',
    INTERESSADO: 'Interessado',
    DESINTERESSADO: 'Desinteressado',
    PROPOSTA: 'Proposta',
    VENDA_REALIZADA: 'Venda realizada',
    VENDA_NAO_REALIZADA: 'Venda não realizada',
  };

  return nomes[tipo] || tipo.replace(/_/g, ' ');
};

const corTipoEstado = (tipo: string) => {
  const cores: Record<string, string> = {
    CONTATO: 'bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300',
    INTERESSADO: 'bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300',
    DESINTERESSADO: 'bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-300',
    PROPOSTA: 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300',
    VENDA_REALIZADA: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300',
    VENDA_NAO_REALIZADA: 'bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-300',
  };

  return cores[tipo] || 'bg-surface-100 text-surface-600 dark:bg-white/10 dark:text-white/60';
};

const corStatus = (status: string) => {
  return status === 'ABERTO'
    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300'
    : 'bg-surface-100 text-surface-500 dark:bg-white/10 dark:text-white/50';
};

const iconeTipoEstado = (tipo: string) => {
  switch (tipo) {
    case 'CONTATO':
      return MessageCircle;
    case 'INTERESSADO':
      return UserRound;
    case 'PROPOSTA':
      return FileText;
    case 'VENDA_REALIZADA':
    case 'VENDA_NAO_REALIZADA':
      return ShoppingBag;
    default:
      return History;
  }
};

const formEstadoInicial = {
  descricao: '',
  forma_pagamento: '',
  valor_total: '',
  quantidade: '',
  data_vencimento: '',
  quant_quitada: '',
};

export default function CRMPage() {
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [pesquisa, setPesquisa] = useState('');
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(false);

  const [clienteSelecionado, setClienteSelecionado] = useState<Cliente | null>(null);
  const [historico, setHistorico] = useState<EstadoCliente[]>([]);
  const [carregandoHistorico, setCarregandoHistorico] = useState(false);

  const [mostrarFormularioEstado, setMostrarFormularioEstado] = useState(false);
  const [salvandoEstado, setSalvandoEstado] = useState(false);

  const [tipoNovoEstado, setTipoNovoEstado] = useState('CONTATO');

  const [formEstado, setFormEstado] = useState(formEstadoInicial);

  const [quitandoVendaId, setQuitandoVendaId] = useState<number | null>(null);

  const carregarClientes = async () => {
    try {
      setCarregando(true);
      setErro(false);

      const response = await api.get<Cliente[]>(
        '/api/v1/integracao/listar-clientes-estados'
      );

      const dados = Array.isArray(response.data) ? response.data : [];

      setClientes(dados);
    } catch (error) {
      console.error('Erro ao carregar clientes:', error);
      setErro(true);
      toast.error('Não foi possível carregar os clientes.');
    } finally {
      setCarregando(false);
    }
  };

  useEffect(() => {
    carregarClientes();
  }, []);

  const clientesFiltrados = useMemo(() => {
    const termo = pesquisa.trim().toLowerCase();

    if (!termo) return clientes;

    return clientes.filter((cliente) => {
      const nome = String(cliente.nome ?? '').toLowerCase();
      const telefone = String(cliente.telefone ?? '').toLowerCase();

      return nome.includes(termo) || telefone.includes(termo);
    });
  }, [clientes, pesquisa]);

  const abrirDetalhes = async (cliente: Cliente) => {
    setClienteSelecionado(cliente);

    // Garante que o formulário comece fechado e limpo para cada cliente.
    setMostrarFormularioEstado(false);
    setTipoNovoEstado('CONTATO');
    setFormEstado(formEstadoInicial);

    // Mostra imediatamente os estados já recebidos na listagem.
    setHistorico(
      Array.isArray(cliente.estados) ? cliente.estados : []
    );

    try {
      setCarregandoHistorico(true);

      const response = await api.get<EstadoCliente[]>(
        `/api/v1/integracao/listar-estados/${cliente.id}`
      );

      const dados = Array.isArray(response.data) ? response.data : [];

      setHistorico(
        [...dados].sort(
          (a, b) =>
            new Date(b.created_at).getTime() -
            new Date(a.created_at).getTime()
        )
      );
    } catch (error) {
      console.error('Erro ao carregar histórico:', error);
      toast.error('Não foi possível atualizar o histórico do cliente.');
    } finally {
      setCarregandoHistorico(false);
    }
  };

  const fecharDetalhes = () => {
    setClienteSelecionado(null);
    setHistorico([]);
    setMostrarFormularioEstado(false);
    setTipoNovoEstado('CONTATO');
    setFormEstado(formEstadoInicial);
  };

  const cadastrarEstado = async (e: FormEvent) => {
    e.preventDefault();

    if (!clienteSelecionado) return;

    if (!formEstado.descricao.trim()) {
      toast.error('Informe uma descrição.');
      return;
    }

    const rotas: Record<string, string> = {
      CONTATO: 'contato-cliente',
      INTERESSADO: 'interessado-cliente',
      DESINTERESSADO: 'desinteressado-cliente',
      PROPOSTA: 'proposta-cliente',
      VENDA_REALIZADA: 'venda-realizada',
      VENDA_NAO_REALIZADA: 'venda-nao-realizada',
    };

    const rota = rotas[tipoNovoEstado];

    if (!rota) {
      toast.error('Tipo de movimentação inválido.');
      return;
    }

    const precisaDadosComerciais =
      tipoNovoEstado === 'PROPOSTA' ||
      tipoNovoEstado === 'VENDA_REALIZADA';

    let payload: Record<string, unknown> = {
      descricao: formEstado.descricao.trim(),
    };

    if (precisaDadosComerciais) {
      const valorTotal = formEstado.valor_total
        ? Number(formEstado.valor_total)
        : null;

      const quantidade = formEstado.quantidade
        ? Number(formEstado.quantidade)
        : null;

      const quantQuitada = formEstado.quant_quitada
        ? Number(formEstado.quant_quitada)
        : null;

      if (valorTotal !== null && (!Number.isFinite(valorTotal) || valorTotal < 0)) {
        toast.error('Informe um valor total válido.');
        return;
      }

      if (quantidade !== null && (!Number.isInteger(quantidade) || quantidade < 1)) {
        toast.error('A quantidade deve ser um número inteiro maior que zero.');
        return;
      }

      if (
        quantQuitada !== null &&
        (!Number.isInteger(quantQuitada) || quantQuitada < 0)
      ) {
        toast.error('A quantidade quitada deve ser um número inteiro válido.');
        return;
      }

      if (
        quantidade !== null &&
        quantQuitada !== null &&
        quantQuitada > quantidade
      ) {
        toast.error('A quantidade quitada não pode superar a quantidade total.');
        return;
      }

      payload = {
        ...payload,
        forma_pagamento: formEstado.forma_pagamento || null,
        valor_total: valorTotal,
        quantidade,
        data_vencimento: formEstado.data_vencimento || null,
        quant_quitada: quantQuitada,
      };
    }

    try {
      setSalvandoEstado(true);

      await api.post(
        `/api/v1/integracao/${rota}/${clienteSelecionado.id}`,
        payload
      );

      toast.success('Movimentação registrada com sucesso!');

      setMostrarFormularioEstado(false);
      setTipoNovoEstado('CONTATO');
      setFormEstado(formEstadoInicial);

      // Atualiza o histórico do cliente.
      try {
        const response = await api.get<EstadoCliente[]>(
          `/api/v1/integracao/listar-estados/${clienteSelecionado.id}`
        );

        const dados = Array.isArray(response.data) ? response.data : [];

        const ordenados = [...dados].sort(
          (a, b) =>
            new Date(b.created_at).getTime() -
            new Date(a.created_at).getTime()
        );

        setHistorico(ordenados);

        setClientes((anteriores) =>
          anteriores.map((cliente) =>
            cliente.id === clienteSelecionado.id
              ? { ...cliente, estados: ordenados }
              : cliente
          )
        );

        setClienteSelecionado((anterior) =>
          anterior ? { ...anterior, estados: ordenados } : null
        );
      } catch (error) {
        console.error('Erro ao atualizar histórico:', error);
        toast.warning('Movimentação salva, mas não foi possível atualizar o histórico.');
      }
    } catch (error: any) {
      console.error('Erro ao cadastrar movimentação:', error);

      const detalhe = error?.response?.data?.detail;

      toast.error(
        typeof detalhe === 'string'
          ? detalhe
          : 'Não foi possível registrar a movimentação.'
      );
    } finally {
      setSalvandoEstado(false);
    }
  };

  const quitarVenda = async (estado: EstadoCliente) => {
    if (!clienteSelecionado || !estado.quantidade) return;

    const quantidadeJaQuitada = estado.quant_quitada ?? 0;
    const quantidadeRestante = estado.quantidade - quantidadeJaQuitada;

    if (quantidadeRestante <= 0) return;

    const resposta = window.prompt(
      `Venda: ${estado.descricao || 'Venda realizada'}\n` +
      `Quantidade total: ${estado.quantidade}\n` +
      `Quantidade já quitada: ${quantidadeJaQuitada}\n` +
      `Quantidade restante: ${quantidadeRestante}\n\n` +
      `Quantas unidades/parcelas deseja quitar?`
    );

    if (resposta === null) return;

    const quantidade = Number(resposta);

    if (
      !Number.isInteger(quantidade) ||
      quantidade <= 0 ||
      quantidade > quantidadeRestante
    ) {
      toast.error(`Informe uma quantidade entre 1 e ${quantidadeRestante}.`);
      return;
    }

    setQuitandoVendaId(estado.id);

    try {
      await api.post(
        `/api/v1/integracao/quitar-venda/${clienteSelecionado.id}/${estado.id}/${quantidade}`
      );

      toast.success('Venda quitada com sucesso!');

      // Atualiza o histórico para mostrar a quantidade quitada e o novo status.
      try {
        const response = await api.get<EstadoCliente[]>(
          `/api/v1/integracao/listar-estados/${clienteSelecionado.id}`
        );

        const estadosAtualizados = [...response.data].sort(
          (a, b) =>
            new Date(b.created_at).getTime() -
            new Date(a.created_at).getTime()
        );

        setHistorico(estadosAtualizados);

        setClienteSelecionado((atual) =>
          atual
            ? { ...atual, estados: estadosAtualizados }
            : atual
        );

        setClientes((atuais) =>
          atuais.map((cliente) =>
            cliente.id === clienteSelecionado.id
              ? { ...cliente, estados: estadosAtualizados }
              : cliente
          )
        );
      } catch {
        toast.error('A venda foi quitada, mas não foi possível atualizar o histórico.');
      }
    } catch (error: any) {
      const detalhe = error?.response?.data?.detail;

      toast.error(
        typeof detalhe === 'string'
          ? detalhe
          : detalhe?.detail || 'Não foi possível quitar a venda.'
      );
    } finally {
      setQuitandoVendaId(null);
    }
  };

  const totalClientes = clientes.length;

  const clientesComVenda = clientes.filter((cliente) =>
    cliente.estados?.some(
      (estado) => estado.tipo === 'VENDA_REALIZADA'
    )
  ).length;

  const clientesComPendencias = clientes.filter((cliente) =>
    cliente.estados?.some(
      (estado) => estado.status === 'ABERTO'
    )
  ).length;

  return (
    <div className="min-h-full space-y-6 pb-8">
      {/* Cabeçalho */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
              <Users className="h-5 w-5" />
            </div>

            <div>
              <h1 className="text-2xl font-bold text-surface-900 dark:text-white">
                CRM
              </h1>
              <p className="text-sm text-surface-500 dark:text-white/50">
                Acompanhe seus clientes e o histórico de relacionamento.
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={carregarClientes}
          disabled={carregando}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-surface-200 bg-white px-4 py-2.5 text-sm font-medium text-surface-700 transition hover:bg-surface-50 disabled:opacity-50 dark:border-white/10 dark:bg-white/5 dark:text-white/80 dark:hover:bg-white/10"
        >
          <RefreshCw className={`h-4 w-4 ${carregando ? 'animate-spin' : ''}`} />
          Atualizar
        </button>
      </div>

      {/* Indicadores */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-surface-200 bg-white p-5 dark:border-white/10 dark:bg-white/[0.03]">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-surface-500 dark:text-white/50">
                Total de clientes
              </p>
              <p className="mt-2 text-2xl font-bold text-surface-900 dark:text-white">
                {carregando ? '—' : totalClientes}
              </p>
            </div>

            <div className="rounded-xl bg-blue-50 p-3 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
              <Users className="h-5 w-5" />
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-surface-200 bg-white p-5 dark:border-white/10 dark:bg-white/[0.03]">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-surface-500 dark:text-white/50">
                Clientes com vendas
              </p>
              <p className="mt-2 text-2xl font-bold text-surface-900 dark:text-white">
                {carregando ? '—' : clientesComVenda}
              </p>
            </div>

            <div className="rounded-xl bg-emerald-50 p-3 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400">
              <ShoppingBag className="h-5 w-5" />
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-surface-200 bg-white p-5 dark:border-white/10 dark:bg-white/[0.03]">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-surface-500 dark:text-white/50">
                Clientes com estados abertos
              </p>
              <p className="mt-2 text-2xl font-bold text-surface-900 dark:text-white">
                {carregando ? '—' : clientesComPendencias}
              </p>
            </div>

            <div className="rounded-xl bg-amber-50 p-3 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400">
              <AlertCircle className="h-5 w-5" />
            </div>
          </div>
        </div>
      </div>

      {/* Pesquisa e listagem */}
      <div className="rounded-2xl border border-surface-200 bg-white dark:border-white/10 dark:bg-white/[0.03]">
        <div className="flex flex-col gap-4 border-b border-surface-100 p-5 dark:border-white/10 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-semibold text-surface-900 dark:text-white">
              Seus clientes
            </h2>
            <p className="mt-1 text-sm text-surface-500 dark:text-white/50">
              Selecione um cliente para visualizar seu histórico.
            </p>
          </div>

          <div className="relative w-full sm:max-w-xs">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />

            <input
              type="text"
              value={pesquisa}
              onChange={(e) => setPesquisa(e.target.value)}
              placeholder="Buscar por nome ou telefone..."
              className="w-full rounded-xl border border-surface-200 bg-surface-50 py-2.5 pl-10 pr-4 text-sm text-surface-900 outline-none transition placeholder:text-surface-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/10 dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder:text-white/30"
            />
          </div>
        </div>

        <div className="p-5">
          {carregando ? (
            <div className="flex flex-col items-center justify-center py-16">
              <Loader2 className="h-8 w-8 animate-spin text-brand-500" />
              <p className="mt-3 text-sm text-surface-500 dark:text-white/50">
                Carregando clientes...
              </p>
            </div>
          ) : erro ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <AlertCircle className="h-10 w-10 text-red-400" />
              <p className="mt-3 font-medium text-surface-800 dark:text-white">
                Não foi possível carregar os clientes.
              </p>
              <button
                onClick={carregarClientes}
                className="mt-4 rounded-xl bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700"
              >
                Tentar novamente
              </button>
            </div>
          ) : clientesFiltrados.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="rounded-2xl bg-surface-100 p-4 dark:bg-white/5">
                <Users className="h-8 w-8 text-surface-400" />
              </div>

              <p className="mt-4 font-medium text-surface-800 dark:text-white">
                {pesquisa
                  ? 'Nenhum cliente encontrado'
                  : 'Nenhum cliente cadastrado'}
              </p>

              <p className="mt-1 text-sm text-surface-500 dark:text-white/50">
                {pesquisa
                  ? 'Tente pesquisar utilizando outro nome ou telefone.'
                  : 'Quando houver clientes cadastrados, eles aparecerão aqui.'}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
              {clientesFiltrados.map((cliente) => {
                const estados = Array.isArray(cliente.estados)
                  ? [...cliente.estados].sort(
                    (a, b) =>
                      new Date(b.created_at).getTime() -
                      new Date(a.created_at).getTime()
                  )
                  : [];

                const estadosRecentes = estados.slice(0, 3);

                const estadosAbertos = estados.filter(
                  (estado) => estado.status === 'ABERTO'
                ).length;

                return (
                  <button
                    key={cliente.id}
                    onClick={() => abrirDetalhes(cliente)}
                    className="group w-full rounded-2xl border border-surface-200 bg-white p-5 text-left transition hover:border-brand-300 hover:shadow-lg hover:shadow-brand-500/5 dark:border-white/10 dark:bg-white/[0.02] dark:hover:border-brand-500/40"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex min-w-0 items-center gap-3">
                        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                          <UserRound className="h-5 w-5" />
                        </div>

                        <div className="min-w-0">
                          <h3 className="truncate font-semibold text-surface-900 dark:text-white">
                            {cliente.nome || 'Cliente sem nome'}
                          </h3>
                          <p className="text-xs text-surface-500 dark:text-white/40">
                            Cliente #{cliente.id}
                          </p>
                        </div>
                      </div>

                      <ChevronRight className="h-5 w-5 shrink-0 text-surface-300 transition group-hover:translate-x-1 group-hover:text-brand-500" />
                    </div>

                    <div className="mt-5 space-y-2">
                      <div className="flex items-center gap-2 text-sm text-surface-600 dark:text-white/60">
                        <Phone className="h-4 w-4 shrink-0 text-surface-400" />
                        <span>{cliente.telefone || 'Telefone não informado'}</span>
                      </div>

                      {cliente.email && (
                        <div className="flex items-center gap-2 text-sm text-surface-600 dark:text-white/60">
                          <Mail className="h-4 w-4 shrink-0 text-surface-400" />
                          <span className="truncate">{cliente.email}</span>
                        </div>
                      )}

                      <div className="flex items-center gap-2 text-sm text-surface-600 dark:text-white/60">
                        <CalendarDays className="h-4 w-4 shrink-0 text-surface-400" />
                        <span>
                          Cadastro em {formatarData(cliente.created_at)}
                        </span>
                      </div>
                    </div>

                    <div className="mt-5 border-t border-surface-100 pt-4 dark:border-white/10">
                      <div className="mb-3 flex items-center justify-between">
                        <span className="text-xs font-semibold uppercase tracking-wide text-surface-400">
                          Atividades recentes
                        </span>

                        <span className="text-xs text-surface-500 dark:text-white/40">
                          {estados.length} registro(s)
                        </span>
                      </div>

                      {estadosRecentes.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {estadosRecentes.map((estado) => (
                            <span
                              key={estado.id}
                              className={`rounded-lg px-2.5 py-1 text-xs font-medium ${corTipoEstado(estado.tipo)}`}
                            >
                              {nomeTipoEstado(estado.tipo)}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-surface-400">
                          Nenhuma atividade registrada.
                        </p>
                      )}

                      <div className="mt-4 flex items-center justify-between">
                        <span className="text-xs text-surface-500 dark:text-white/40">
                          {estadosAbertos} estado(s) aberto(s)
                        </span>

                        <span className="text-xs font-medium text-brand-600 dark:text-brand-400">
                          Ver detalhes
                        </span>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Painel de detalhes */}
      {clienteSelecionado && (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-black/50 backdrop-blur-sm"
          onClick={fecharDetalhes}
        >
          <div
            className="flex h-full w-full max-w-2xl flex-col overflow-hidden bg-white shadow-2xl dark:bg-surface-900"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Cabeçalho do painel */}
            <div className="flex items-center justify-between border-b border-surface-200 p-5 dark:border-white/10">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-brand-600 dark:text-brand-400">
                  Perfil do cliente
                </p>
                <h2 className="mt-1 text-xl font-bold text-surface-900 dark:text-white">
                  {clienteSelecionado.nome}
                </h2>
              </div>

              <button
                onClick={fecharDetalhes}
                className="rounded-xl p-2 text-surface-400 transition hover:bg-surface-100 hover:text-surface-700 dark:hover:bg-white/10 dark:hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Conteúdo */}
            <div className="flex-1 overflow-y-auto p-5">
              {/* Dados do cliente */}
              <div className="rounded-2xl border border-surface-200 bg-surface-50 p-5 dark:border-white/10 dark:bg-white/[0.03]">
                <h3 className="mb-4 text-sm font-semibold text-surface-900 dark:text-white">
                  Informações
                </h3>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <p className="text-xs text-surface-400">Nome</p>
                    <p className="mt-1 text-sm font-medium text-surface-800 dark:text-white">
                      {clienteSelecionado.nome}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs text-surface-400">Telefone</p>
                    <p className="mt-1 text-sm font-medium text-surface-800 dark:text-white">
                      {clienteSelecionado.telefone || 'Não informado'}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs text-surface-400">E-mail</p>
                    <p className="mt-1 break-all text-sm font-medium text-surface-800 dark:text-white">
                      {clienteSelecionado.email || 'Não informado'}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs text-surface-400">Data de cadastro</p>
                    <p className="mt-1 text-sm font-medium text-surface-800 dark:text-white">
                      {formatarData(clienteSelecionado.created_at)}
                    </p>
                  </div>
                </div>
              </div>

              {/* Adicionar movimentação */}
              <div className="mt-7">
                {!mostrarFormularioEstado ? (
                  <button
                    onClick={() => setMostrarFormularioEstado(true)}
                    className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-brand-700"
                  >
                    <Plus className="h-4 w-4" />
                    Adicionar movimentação
                  </button>
                ) : (
                  <form
                    onSubmit={cadastrarEstado}
                    className="rounded-2xl border border-brand-200 bg-brand-50/50 p-5 dark:border-brand-500/20 dark:bg-brand-500/5"
                  >
                    <div className="mb-5 flex items-center justify-between">
                      <h3 className="font-semibold text-surface-900 dark:text-white">
                        Nova movimentação
                      </h3>

                      <button
                        type="button"
                        onClick={() => setMostrarFormularioEstado(false)}
                        className="rounded-lg p-2 text-surface-400 hover:bg-surface-100 dark:hover:bg-white/10"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>

                    <div className="space-y-4">
                      <div>
                        <label className="mb-1.5 block text-sm font-medium text-surface-700 dark:text-white/80">
                          Tipo de movimentação
                        </label>

                        <select
                          value={tipoNovoEstado}
                          onChange={(e) => setTipoNovoEstado(e.target.value)}
                          className="w-full rounded-xl border border-surface-200 bg-white px-3 py-2.5 text-sm text-surface-900 outline-none focus:border-brand-500 dark:border-white/10 dark:bg-surface-900 dark:text-white"
                        >
                          <option value="CONTATO">Contato</option>
                          <option value="INTERESSADO">Interessado</option>
                          <option value="DESINTERESSADO">Desinteressado</option>
                          <option value="PROPOSTA">Proposta</option>
                          <option value="VENDA_REALIZADA">Venda realizada</option>
                          <option value="VENDA_NAO_REALIZADA">Venda não realizada</option>
                        </select>
                      </div>

                      <div>
                        <label className="mb-1.5 block text-sm font-medium text-surface-700 dark:text-white/80">
                          Descrição
                        </label>

                        <textarea
                          value={formEstado.descricao}
                          onChange={(e) =>
                            setFormEstado({
                              ...formEstado,
                              descricao: e.target.value,
                            })
                          }
                          rows={3}
                          placeholder="Descreva o que aconteceu com este cliente..."
                          className="w-full resize-none rounded-xl border border-surface-200 bg-white px-3 py-2.5 text-sm text-surface-900 outline-none focus:border-brand-500 dark:border-white/10 dark:bg-surface-900 dark:text-white"
                        />
                      </div>

                      {(tipoNovoEstado === 'PROPOSTA' ||
                        tipoNovoEstado === 'VENDA_REALIZADA') && (
                          <>
                            <div>
                              <label className="mb-1.5 block text-sm font-medium text-surface-700 dark:text-white/80">
                                Forma de pagamento
                              </label>

                              <select
                                value={formEstado.forma_pagamento}
                                onChange={(e) =>
                                  setFormEstado({
                                    ...formEstado,
                                    forma_pagamento: e.target.value,
                                  })
                                }
                                className="w-full rounded-xl border border-surface-200 bg-white px-3 py-2.5 text-sm text-surface-900 outline-none focus:border-brand-500 dark:border-white/10 dark:bg-surface-900 dark:text-white"
                              >
                                <option value="">Não informado</option>
                                <option value="dinheiro">Dinheiro</option>
                                <option value="pix">Pix</option>
                                <option value="cartao_credito">Cartão de crédito</option>
                                <option value="cartao_debito">Cartão de débito</option>
                                <option value="crediario">Crediário</option>
                                <option value="transferencia">Transferência</option>
                              </select>
                            </div>

                            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                              <div>
                                <label className="mb-1.5 block text-sm font-medium text-surface-700 dark:text-white/80">
                                  Valor total (R$)
                                </label>

                                <input
                                  type="number"
                                  min="0"
                                  step="0.01"
                                  value={formEstado.valor_total}
                                  onChange={(e) =>
                                    setFormEstado({
                                      ...formEstado,
                                      valor_total: e.target.value,
                                    })
                                  }
                                  placeholder="0,00"
                                  className="w-full rounded-xl border border-surface-200 bg-white px-3 py-2.5 text-sm text-surface-900 outline-none focus:border-brand-500 dark:border-white/10 dark:bg-surface-900 dark:text-white"
                                />
                              </div>

                              <div>
                                <label className="mb-1.5 block text-sm font-medium text-surface-700 dark:text-white/80">
                                  Quantidade
                                </label>

                                <input
                                  type="number"
                                  min="1"
                                  step="1"
                                  value={formEstado.quantidade}
                                  onChange={(e) =>
                                    setFormEstado({
                                      ...formEstado,
                                      quantidade: e.target.value,
                                    })
                                  }
                                  placeholder="Quantidade"
                                  className="w-full rounded-xl border border-surface-200 bg-white px-3 py-2.5 text-sm text-surface-900 outline-none focus:border-brand-500 dark:border-white/10 dark:bg-surface-900 dark:text-white"
                                />
                              </div>

                              <div>
                                <label className="mb-1.5 block text-sm font-medium text-surface-700 dark:text-white/80">
                                  Quantidade quitada
                                </label>

                                <input
                                  type="number"
                                  min="0"
                                  step="1"
                                  value={formEstado.quant_quitada}
                                  onChange={(e) =>
                                    setFormEstado({
                                      ...formEstado,
                                      quant_quitada: e.target.value,
                                    })
                                  }
                                  placeholder="0"
                                  className="w-full rounded-xl border border-surface-200 bg-white px-3 py-2.5 text-sm text-surface-900 outline-none focus:border-brand-500 dark:border-white/10 dark:bg-surface-900 dark:text-white"
                                />
                              </div>

                              <div>
                                <label className="mb-1.5 block text-sm font-medium text-surface-700 dark:text-white/80">
                                  Data de vencimento
                                </label>

                                <input
                                  type="date"
                                  value={formEstado.data_vencimento}
                                  onChange={(e) =>
                                    setFormEstado({
                                      ...formEstado,
                                      data_vencimento: e.target.value,
                                    })
                                  }
                                  className="w-full rounded-xl border border-surface-200 bg-white px-3 py-2.5 text-sm text-surface-900 outline-none focus:border-brand-500 dark:border-white/10 dark:bg-surface-900 dark:text-white"
                                />
                              </div>
                            </div>
                          </>
                        )}
                    </div>

                    <div className="mt-5 flex gap-3">
                      <button
                        type="button"
                        onClick={() => setMostrarFormularioEstado(false)}
                        disabled={salvandoEstado}
                        className="flex-1 rounded-xl border border-surface-200 py-2.5 text-sm font-medium text-surface-700 transition hover:bg-surface-100 dark:border-white/10 dark:text-white/70 dark:hover:bg-white/10"
                      >
                        Cancelar
                      </button>

                      <button
                        type="submit"
                        disabled={salvandoEstado}
                        className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-brand-600 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {salvandoEstado ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Save className="h-4 w-4" />
                        )}

                        {salvandoEstado ? 'Salvando...' : 'Salvar movimentação'}
                      </button>
                    </div>
                  </form>
                )}
              </div>

              {/* Histórico */}
              <div className="mt-7">
                <div className="mb-5 flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-surface-900 dark:text-white">
                      Histórico do cliente
                    </h3>
                    <p className="mt-1 text-xs text-surface-500 dark:text-white/40">
                      Todas as atividades registradas.
                    </p>
                  </div>

                  <span className="rounded-lg bg-surface-100 px-3 py-1.5 text-xs font-medium text-surface-600 dark:bg-white/10 dark:text-white/60">
                    {historico.length} registro(s)
                  </span>
                </div>

                {carregandoHistorico && (
                  <div className="mb-4 flex items-center gap-2 text-sm text-brand-600 dark:text-brand-400">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Atualizando histórico...
                  </div>
                )}

                {historico.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-surface-200 py-12 text-center dark:border-white/10">
                    <History className="mx-auto h-8 w-8 text-surface-300" />
                    <p className="mt-3 text-sm text-surface-500 dark:text-white/50">
                      Nenhuma atividade encontrada.
                    </p>
                  </div>
                ) : (
                  <div className="relative space-y-4">
                    {historico.map((estado) => {
                      const Icone = iconeTipoEstado(estado.tipo);

                      return (
                        <div
                          key={estado.id}
                          className="relative rounded-2xl border border-surface-200 p-4 dark:border-white/10"
                        >
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div className="flex items-center gap-3">
                              <div className="rounded-xl bg-surface-100 p-2.5 text-surface-600 dark:bg-white/10 dark:text-white/70">
                                <Icone className="h-4 w-4" />
                              </div>

                              <div>
                                <p className="font-semibold text-surface-900 dark:text-white">
                                  {nomeTipoEstado(estado.tipo)}
                                </p>
                                <p className="mt-0.5 text-xs text-surface-400">
                                  {formatarDataHora(estado.created_at)}
                                </p>
                              </div>
                            </div>

                            <span
                              className={`rounded-lg px-2.5 py-1 text-xs font-semibold ${corStatus(estado.status)}`}
                            >
                              {estado.status}
                            </span>
                          </div>

                          {estado.descricao && (
                            <div className="mt-4 rounded-xl bg-surface-50 p-3 dark:bg-white/[0.03]">
                              <p className="text-xs font-medium text-surface-400">
                                Descrição
                              </p>
                              <p className="mt-1 whitespace-pre-wrap text-sm text-surface-700 dark:text-white/70">
                                {estado.descricao}
                              </p>
                            </div>
                          )}

                          {(estado.valor_total != null ||
                            estado.valor_unitario != null ||
                            estado.quantidade != null ||
                            estado.forma_pagamento ||
                            estado.quant_quitada != null ||
                            estado.data_vencimento) && (
                              <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
                                {estado.valor_total != null && (
                                  <div>
                                    <p className="text-xs text-surface-400">
                                      Valor total
                                    </p>
                                    <p className="mt-1 text-sm font-semibold text-surface-900 dark:text-white">
                                      {formatarMoeda(estado.valor_total)}
                                    </p>
                                  </div>
                                )}

                                {estado.valor_unitario != null && (
                                  <div>
                                    <p className="text-xs text-surface-400">
                                      Valor unitário
                                    </p>
                                    <p className="mt-1 text-sm font-medium text-surface-800 dark:text-white/80">
                                      {formatarMoeda(estado.valor_unitario)}
                                    </p>
                                  </div>
                                )}

                                {estado.quantidade != null && (
                                  <div>
                                    <p className="text-xs text-surface-400">
                                      Quantidade
                                    </p>
                                    <p className="mt-1 text-sm font-medium text-surface-800 dark:text-white/80">
                                      {estado.quantidade}
                                    </p>
                                  </div>
                                )}

                                {estado.forma_pagamento && (
                                  <div>
                                    <p className="text-xs text-surface-400">
                                      Forma de pagamento
                                    </p>
                                    <p className="mt-1 text-sm font-medium capitalize text-surface-800 dark:text-white/80">
                                      {estado.forma_pagamento}
                                    </p>
                                  </div>
                                )}

                                {estado.quant_quitada != null && (
                                  <div>
                                    <p className="text-xs text-surface-400">
                                      Quantidade quitada
                                    </p>
                                    <p className="mt-1 text-sm font-medium text-surface-800 dark:text-white/80">
                                      {estado.quant_quitada}
                                      {estado.quantidade != null
                                        ? ` / ${estado.quantidade}`
                                        : ''}
                                    </p>
                                  </div>
                                )}

                                {estado.data_vencimento && (
                                  <div>
                                    <p className="text-xs text-surface-400">
                                      Vencimento
                                    </p>
                                    <p className="mt-1 text-sm font-medium text-surface-800 dark:text-white/80">
                                      {formatarData(estado.data_vencimento)}
                                    </p>
                                  </div>
                                )}
                              </div>
                            )}

                          {estado.tipo === 'VENDA_REALIZADA' &&
                            estado.status === 'ABERTO' &&
                            estado.quantidade != null && (
                              <div className="mt-5 border-t border-surface-200 pt-4 dark:border-white/10">
                                <div className="mb-3 flex items-center justify-between gap-3">
                                  <div>
                                    <p className="text-sm font-medium text-surface-900 dark:text-white">
                                      Pagamento da venda
                                    </p>

                                    <p className="mt-1 text-xs text-surface-500 dark:text-white/50">
                                      {estado.quant_quitada ?? 0} de {estado.quantidade} quitada(s)
                                    </p>
                                  </div>

                                  <span className="text-sm font-semibold text-surface-700 dark:text-white/80">
                                    Restam {estado.quantidade - (estado.quant_quitada ?? 0)}
                                  </span>
                                </div>

                                <button
                                  type="button"
                                  onClick={() => quitarVenda(estado)}
                                  disabled={quitandoVendaId === estado.id}
                                  className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  {quitandoVendaId === estado.id ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                  ) : (
                                    <ShoppingBag className="h-4 w-4" />
                                  )}

                                  {quitandoVendaId === estado.id
                                    ? 'Quitando...'
                                    : 'Quitar venda / parcela'}
                                </button>
                              </div>
                            )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* Rodapé */}
            <div className="border-t border-surface-200 p-4 dark:border-white/10">
              <button
                onClick={fecharDetalhes}
                className="w-full rounded-xl border border-surface-200 py-2.5 text-sm font-medium text-surface-700 transition hover:bg-surface-50 dark:border-white/10 dark:text-white/70 dark:hover:bg-white/5"
              >
                Fechar detalhes
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
