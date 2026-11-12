import { useEffect, useState } from 'react';
import {
  Activity,
  Users,
  Clock,
  CalendarClock,
  AlertCircle,
  CheckCircle,
  XCircle,
  RefreshCw,
  CreditCard,
} from 'lucide-react';

import { useAuth } from '@/providers/AuthProvider';
import { api } from '@/lib/api';
import { StatCard } from '@/components/ui/StatCard';
import { Card, CardBody } from '@/components/ui/Card';

interface EstadoAberto {
  id: number;
  client_id: number;
  nome: string;
  telefone: string | null;
  email: string | null;
  tipo: string;
  status: string;
  descricao: string | null;
  created_at: string;
  dias_aberto: number;
}

interface Pagamento {
  id_venda: number;
  client_id: number;
  nome: string;
  telefone: string | null;
  email: string | null;
  descricao: string | null;
  quantidade: number;
  quant_quitada: number;
  proxima_parcela: number;
  valor_parcela: number | string | null;
  valor_total: number | string | null;
  data_vencimento: string | null;
  dias_vencimento: number | null;
  situacao: string;
}

interface DashboardAcompanhamento {
  estados_abertos: EstadoAberto[];
  pagamentos: Pagamento[];
}

interface Cliente {
  id: number;
}

export default function DashboardPage() {
  const { user } = useAuth();

  const [data, setData] = useState<DashboardAcompanhamento>({
    estados_abertos: [],
    pagamentos: [],
  });

  const [totalClientes, setTotalClientes] = useState(0);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [mensagem, setMensagem] = useState('');

  const carregarDashboard = async () => {
    setLoading(true);
    setErro('');

    try {
      const [dashboardResponse, clientesResponse] = await Promise.all([
        api.get<DashboardAcompanhamento>(
          '/api/v1/integracao/dashboard-acompanhamento'
        ),
        api.get<Cliente[]>('/api/v1/integracao/listar-clientes').catch(
          (error) => {
            if (error.response?.status === 404) {
              return { data: [] as Cliente[] };
            }
            throw error;
          }
        ),
      ]);

      setData({
        estados_abertos: dashboardResponse.data.estados_abertos || [],
        pagamentos: dashboardResponse.data.pagamentos || [],
      });

      setTotalClientes(clientesResponse.data.length);

    } catch (error: any) {
      setErro(
        error.response?.data?.detail ||
        'Não foi possível carregar os dados do dashboard.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    carregarDashboard();
  }, []);

  const fecharEstado = async (idEstado: number) => {
    const confirmar = window.confirm(
      'Deseja realmente encerrar esta etapa?'
    );

    if (!confirmar) return;

    setActionLoading(`estado-${idEstado}`);
    setMensagem('');

    try {
      await api.post(
        `/api/v1/integracao/fechar-estado/${idEstado}`
      );

      setMensagem('Etapa encerrada com sucesso!');
      await carregarDashboard();

    } catch (error: any) {
      setErro(
        error.response?.data?.detail ||
        'Não foi possível encerrar a etapa.'
      );
    } finally {
      setActionLoading(null);
    }
  };

  const quitarPagamento = async (
    pagamento: Pagamento
  ) => {
    const confirmar = window.confirm(
      `Deseja registrar o pagamento da parcela ${pagamento.proxima_parcela}?`
    );

    if (!confirmar) return;

    setActionLoading(`pagamento-${pagamento.id_venda}`);
    setMensagem('');

    try {
      await api.post(
        `/api/v1/integracao/quitar-venda/${pagamento.client_id}/${pagamento.id_venda}/1`
      );

      setMensagem('Pagamento registrado com sucesso!');
      await carregarDashboard();

    } catch (error: any) {
      setErro(
        error.response?.data?.detail ||
        'Não foi possível registrar o pagamento.'
      );
    } finally {
      setActionLoading(null);
    }
  };

  const cancelarVenda = async (pagamento: Pagamento) => {
    const confirmar = window.confirm(
      `Deseja realmente cancelar a venda de ${pagamento.nome}?`
    );

    if (!confirmar) return;

    setActionLoading(`cancelamento-${pagamento.id_venda}`);
    setMensagem('');

    try {
      await api.post(
        `/api/v1/integracao/cancelar-venda/${pagamento.client_id}/${pagamento.id_venda}`
      );

      setMensagem('Venda cancelada com sucesso!');
      await carregarDashboard();

    } catch (error: any) {
      setErro(
        error.response?.data?.detail ||
        'Não foi possível cancelar a venda.'
      );
    } finally {
      setActionLoading(null);
    }
  };

  const formatarData = (data: string | null) => {
    if (!data) return 'Não informada';

    const [ano, mes, dia] = data.substring(0, 10).split('-');

    return `${dia}/${mes}/${ano}`;
  };

  const formatarValor = (valor: number | string | null) => {
    return Number(valor || 0).toLocaleString('pt-BR', {
      style: 'currency',
      currency: 'BRL',
    });
  };

  const formatarDias = (dias: number) => {
    if (dias === 0) return 'Hoje';
    if (dias === 1) return '1 dia';
    return `${dias} dias`;
  };

  const estadosAbertos = data.estados_abertos;

  const pagamentos = data.pagamentos;

  const proximosPagamentos = pagamentos.filter(
    (pagamento) =>
      pagamento.dias_vencimento !== null &&
      pagamento.dias_vencimento >= 0 &&
      pagamento.dias_vencimento <= 7
  );

  const pagamentosAtrasados = pagamentos.filter(
    (pagamento) => pagamento.situacao === 'ATRASADO'
  );

  const getTipoEstado = (tipo: string) => {
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

  const getSituacaoPagamento = (pagamento: Pagamento) => {
    if (pagamento.situacao === 'ATRASADO') {
      return {
        texto: 'Pagamento atrasado',
        cor: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
      };
    }

    if (pagamento.situacao === 'VENCE_HOJE') {
      return {
        texto: 'Vence hoje',
        cor: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
      };
    }

    if (pagamento.situacao === 'A_VENCER') {
      return {
        texto: 'A vencer',
        cor: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
      };
    }

    return {
      texto: 'Sem vencimento',
      cor: 'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-white/60',
    };
  };

  return (
    <div className="space-y-8">

      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-white">
            Olá, {user?.full_name?.split(' ')[0] || 'bem-vindo'}! 👋
          </h1>

          <p className="text-surface-500 dark:text-white/60 mt-1">
            Acompanhe os clientes e pagamentos que precisam da sua atenção.
          </p>
        </div>

        <button
          onClick={carregarDashboard}
          disabled={loading}
          className="p-2 rounded-lg border border-surface-200 dark:border-surface-700 hover:bg-surface-100 dark:hover:bg-surface-800 transition"
          title="Atualizar dashboard"
        >
          <RefreshCw
            className={`w-5 h-5 text-surface-600 dark:text-white/70 ${
              loading ? 'animate-spin' : ''
            }`}
          />
        </button>
      </div>

      {/* Messages */}
      {erro && (
        <div className="p-3 rounded-lg bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400 text-sm">
          {erro}
        </div>
      )}

      {mensagem && (
        <div className="p-3 rounded-lg bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400 text-sm">
          {mensagem}
        </div>
      )}

      {/* Stats cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">

        <StatCard
          icon={Users}
          label="Total de clientes"
          value={loading ? '...' : totalClientes.toLocaleString('pt-BR')}
        />

        <StatCard
          icon={Activity}
          label="Etapas em aberto"
          value={loading ? '...' : estadosAbertos.length.toLocaleString('pt-BR')}
          gradient
        />

        <StatCard
          icon={CalendarClock}
          label="Pagamentos a vencer"
          value={loading ? '...' : proximosPagamentos.length.toLocaleString('pt-BR')}
        />

        <StatCard
          icon={AlertCircle}
          label="Pagamentos atrasados"
          value={loading ? '...' : pagamentosAtrasados.length.toLocaleString('pt-BR')}
        />

      </div>

      {/* Stage tracking */}
      <div className="space-y-4">

        <div>
          <h2 className="text-lg font-semibold text-surface-900 dark:text-white">
            Clientes com etapas em aberto
          </h2>

          <p className="text-sm text-surface-500 dark:text-white/60 mt-1">
            Clientes que ainda têm etapas de venda em andamento.
          </p>
        </div>

        {loading ? (
          <Card>
            <CardBody>
              <p className="text-center text-surface-500 py-6">
                Carregando acompanhamentos...
              </p>
            </CardBody>
          </Card>
        ) : estadosAbertos.length === 0 ? (
          <Card>
            <CardBody>
              <div className="text-center py-8">
                <CheckCircle className="w-10 h-10 mx-auto text-green-500 mb-3" />

                <p className="font-medium text-surface-900 dark:text-white">
                  Nenhuma etapa em aberto
                </p>

                <p className="text-sm text-surface-500 mt-1">
                  Nenhum cliente precisa de acompanhamento no momento.
                </p>
              </div>
            </CardBody>
          </Card>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

            {estadosAbertos.map((estado) => (
              <Card key={estado.id}>
                <CardBody>

                  <div className="flex items-start justify-between gap-3">

                    <div>
                      <h3 className="font-semibold text-surface-900 dark:text-white">
                        {estado.nome}
                      </h3>

                      <p className="text-sm text-surface-500 mt-1">
                        {estado.telefone || 'Telefone não informado'}
                      </p>
                    </div>

                    <span className="px-3 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 whitespace-nowrap">
                      {getTipoEstado(estado.tipo)}
                    </span>

                  </div>

                  <div className="my-5">

                    <p className="text-3xl font-bold text-surface-900 dark:text-white">
                      {formatarDias(estado.dias_aberto)}
                    </p>

                    <p className="text-sm text-surface-500 mt-1">
                      {estado.tipo === 'INTERESSADO'
                        ? 'O cliente continua interessado.'
                        : estado.tipo === 'PROPOSTA'
                        ? 'A proposta continua em aberto.'
                        : `A etapa "${getTipoEstado(estado.tipo).toLowerCase()}" continua em aberto.`}
                    </p>

                  </div>

                  {estado.descricao && (
                    <p className="text-sm text-surface-600 dark:text-white/60 mb-3">
                      {estado.descricao}
                    </p>
                  )}

                  <div className="flex items-center justify-between text-xs text-surface-500 border-t border-surface-200 dark:border-surface-700 pt-3">
                    <span>
                      Criado em {formatarData(estado.created_at)}
                    </span>

                    <span>Etapa em aberto</span>
                  </div>

                  <div className="flex gap-2 mt-4">

                    <button
                      onClick={() => fecharEstado(estado.id)}
                      disabled={actionLoading === `estado-${estado.id}`}
                      className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white text-sm font-medium transition disabled:opacity-50"
                    >
                      <CheckCircle className="w-4 h-4" />

                      {actionLoading === `estado-${estado.id}`
                        ? 'Encerrando...'
                        : 'Encerrar etapa'}
                    </button>

                  </div>

                </CardBody>
              </Card>
            ))}

          </div>
        )}

      </div>

      {/* Acompanhamento de pagamentos */}
      <div className="space-y-4">

        <div>
          <h2 className="text-lg font-semibold text-surface-900 dark:text-white">
            Acompanhamento de pagamentos
          </h2>

          <p className="text-sm text-surface-500 dark:text-white/60 mt-1">
            Acompanhe as parcelas próximas do vencimento e os pagamentos em atraso.
          </p>
        </div>

        {loading ? (
          <Card>
            <CardBody>
              <p className="text-center text-surface-500 py-6">
                Carregando pagamentos...
              </p>
            </CardBody>
          </Card>
        ) : pagamentos.length === 0 ? (
          <Card>
            <CardBody>
              <div className="text-center py-8">
                <CreditCard className="w-10 h-10 mx-auto text-surface-400 mb-3" />

                <p className="font-medium text-surface-900 dark:text-white">
                  Nenhum pagamento pendente
                </p>

                <p className="text-sm text-surface-500 mt-1">
                  Não há vendas com parcelas pendentes.
                </p>
              </div>
            </CardBody>
          </Card>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

            {pagamentos.map((pagamento) => {
              const situacao = getSituacaoPagamento(pagamento);

              return (
                <Card key={pagamento.id_venda}>
                  <CardBody>

                    <div className="flex items-start justify-between gap-3">

                      <div>
                        <h3 className="font-semibold text-surface-900 dark:text-white">
                          {pagamento.nome}
                        </h3>

                        <p className="text-sm text-surface-500 mt-1">
                          {pagamento.telefone || 'Telefone não informado'}
                        </p>
                      </div>

                      <span className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap ${situacao.cor}`}>
                        {situacao.texto}
                      </span>

                    </div>

                    <p className="text-xs text-surface-500 mt-3">
                      Venda nº {pagamento.id_venda} · {pagamento.quantidade} {pagamento.quantidade === 1 ? 'parcela' : 'parcelas'} · {pagamento.quant_quitada} {pagamento.quant_quitada === 1 ? 'paga' : 'pagas'}
                    </p>

                    <div className="my-5">

                      <p className={`text-3xl font-bold ${
                        pagamento.situacao === 'ATRASADO'
                          ? 'text-red-500'
                          : 'text-surface-900 dark:text-white'
                      }`}>
                        {pagamento.dias_vencimento === null
                          ? 'Sem data'
                          : pagamento.dias_vencimento < 0
                          ? formatarDias(Math.abs(pagamento.dias_vencimento))
                          : pagamento.dias_vencimento === 0
                          ? 'Hoje'
                          : formatarDias(pagamento.dias_vencimento)}
                      </p>

                      <p className="text-sm text-surface-500 mt-1">
                        {pagamento.situacao === 'ATRASADO'
                          ? 'Este pagamento está atrasado.'
                          : pagamento.situacao === 'VENCE_HOJE'
                          ? 'O pagamento vence hoje.'
                          : pagamento.situacao === 'A_VENCER'
                          ? 'Prazo restante até o próximo vencimento.'
                          : 'Esta venda não tem data de vencimento.'}
                      </p>

                    </div>

                    <div className="space-y-2 border-t border-surface-200 dark:border-surface-700 pt-3">

                      <div className="flex justify-between text-sm">
                        <span className="text-surface-500">
                          Próxima parcela
                        </span>

                        <span className="font-medium text-surface-900 dark:text-white">
                          {pagamento.proxima_parcela}/{pagamento.quantidade}
                        </span>
                      </div>

                      <div className="flex justify-between text-sm">
                        <span className="text-surface-500">
                          Valor da parcela
                        </span>

                        <span className="font-semibold text-surface-900 dark:text-white">
                          {formatarValor(pagamento.valor_parcela)}
                        </span>
                      </div>

                      <div className="flex justify-between text-sm">
                        <span className="text-surface-500">
                          Vencimento
                        </span>

                        <span className="font-medium text-surface-900 dark:text-white">
                          {formatarData(pagamento.data_vencimento)}
                        </span>
                      </div>

                    </div>

                    <div className="flex flex-col sm:flex-row gap-2 mt-4">

                      <button
                        onClick={() => quitarPagamento(pagamento)}
                        disabled={actionLoading === `pagamento-${pagamento.id_venda}`}
                        className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white text-sm font-medium transition disabled:opacity-50"
                      >
                        <CheckCircle className="w-4 h-4" />

                        {actionLoading === `pagamento-${pagamento.id_venda}`
                          ? 'Processando...'
                          : 'Registrar pagamento'}
                      </button>

                      <button
                        onClick={() => cancelarVenda(pagamento)}
                        disabled={actionLoading === `cancelamento-${pagamento.id_venda}`}
                        className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-red-300 text-red-600 hover:bg-red-50 dark:border-red-900 dark:hover:bg-red-900/20 text-sm font-medium transition disabled:opacity-50"
                      >
                        <XCircle className="w-4 h-4" />

                        {actionLoading === `cancelamento-${pagamento.id_venda}`
                          ? 'Cancelando...'
                          : 'Cancelar venda'}
                      </button>

                    </div>

                  </CardBody>
                </Card>
              );
            })}

          </div>
        )}

      </div>

    </div>
  );
}
