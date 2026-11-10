
import { useEffect, useMemo, useState, type FormEvent } from 'react';
import {
  Search,
  Users,
  RefreshCw,
  Plus,
  Pencil,
  X,
  UserRound,
  UserCheck,
  UserX,
  Save,
} from 'lucide-react';
import { toast } from 'sonner';
import { isAxiosError } from 'axios';
import { api } from '@/lib/api';

interface Cliente {
  id: number;
  nome: string;
  email?: string | null;
  telefone?: string | null;
  status?: boolean | null;
}

export default function CustomersPage() {
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [busca, setBusca] = useState('');
  const [carregando, setCarregando] = useState(true);

  const [mostrarInativos, setMostrarInativos] = useState(false);

  const [modal, setModal] = useState<'criar' | 'editar' | null>(null);
  const [clienteSelecionado, setClienteSelecionado] = useState<Cliente | null>(null);

  const [nome, setNome] = useState('');
  const [email, setEmail] = useState('');
  const [telefone, setTelefone] = useState('');
  const [salvando, setSalvando] = useState(false);

  const carregarClientes = async () => {
    setCarregando(true);

    try {
      const response = await api.get<Cliente[]>(
        '/api/v1/integracao/listar-clientes'
      );

      setClientes(response.data);
    } catch (error: unknown) {
      if (isAxiosError(error) && error.response?.status === 404) {
        setClientes([]);
      } else {
        toast.error('Não foi possível carregar os clientes.');
      }
    } finally {
      setCarregando(false);
    }
  };

  useEffect(() => {
    carregarClientes();
  }, []);

  const clientesDaCategoria = useMemo(() => {
    return clientes.filter((cliente) => {
      if (mostrarInativos) {
        return cliente.status === false;
      }

      return cliente.status !== false;
    });
  }, [clientes, mostrarInativos]);

  const clientesFiltrados = useMemo(() => {
    const termo = busca.toLowerCase().trim();

    return clientesDaCategoria.filter((cliente) =>
      [
        cliente.nome,
        cliente.email ?? '',
        cliente.telefone ?? '',
      ].some((campo) => campo.toLowerCase().includes(termo))
    );
  }, [clientesDaCategoria, busca]);

  const abrirCadastro = () => {
    setNome('');
    setEmail('');
    setTelefone('');
    setClienteSelecionado(null);
    setModal('criar');
  };

  const abrirEdicao = (cliente: Cliente) => {
    setClienteSelecionado(cliente);
    setNome(cliente.nome);
    setTelefone(cliente.telefone ?? '');
    setEmail(cliente.email ?? '');
    setModal('editar');
  };

  const fecharModal = () => {
    setModal(null);
    setClienteSelecionado(null);
  };

  const cadastrarCliente = async (e: FormEvent) => {
    e.preventDefault();

    if (!nome.trim() || !telefone.trim()) {
      toast.error('Preencha o nome e o telefone.');
      return;
    }

    setSalvando(true);

    try {
      await api.post('/api/v1/integracao/cadastro-cliente', {
        nome: nome.trim(),
        telefone: telefone.trim(),
        email: email.trim() || null,
        status: true,
      });

      toast.success('Cliente cadastrado com sucesso!');
      fecharModal();
      await carregarClientes();
    } catch (error: unknown) {
      if (isAxiosError(error)) {
        const detalhe = error.response?.data?.detail;

        toast.error(
          typeof detalhe === 'string'
            ? detalhe
            : 'Não foi possível cadastrar o cliente.'
        );
      } else {
        toast.error('Não foi possível cadastrar o cliente.');
      }
    } finally {
      setSalvando(false);
    }
  };

  const editarCliente = async (e: FormEvent) => {
    e.preventDefault();

    if (!clienteSelecionado) return;

    if (!nome.trim() || !telefone.trim()) {
      toast.error('Nome e telefone não podem ficar vazios.');
      return;
    }

    setSalvando(true);

    try {
      const nomeMudou = nome.trim() !== clienteSelecionado.nome;

      const telefoneMudou =
        telefone.trim() !== (clienteSelecionado.telefone ?? '');

      const emailMudou =
        email.trim() !== (clienteSelecionado.email ?? '');

      if (!nomeMudou && !telefoneMudou && !emailMudou) {
        toast.info('Nenhuma alteração foi realizada.');
        fecharModal();
        return;
      }

      if (nomeMudou) {
        await api.put(
          `/api/v1/integracao/editar-nome-cliente/${clienteSelecionado.id}`,
          { nome: nome.trim() }
        );
      }

      if (telefoneMudou) {
        await api.put(
          `/api/v1/integracao/editar-telefone-cliente/${clienteSelecionado.id}`,
          { telefone: telefone.trim() }
        );
      }

      if (emailMudou) {
        await api.put(
          `/api/v1/integracao/editar-email-cliente/${clienteSelecionado.id}`,
          { email: email.trim() }
        );
      }

      toast.success('Cliente atualizado com sucesso!');
      fecharModal();
      await carregarClientes();
    } catch (error: unknown) {
      if (isAxiosError(error)) {
        const detalhe = error.response?.data?.detail;

        toast.error(
          typeof detalhe === 'string'
            ? detalhe
            : 'Não foi possível atualizar o cliente.'
        );
      } else {
        toast.error('Não foi possível atualizar o cliente.');
      }

      await carregarClientes();
    } finally {
      setSalvando(false);
    }
  };

  const desativarCliente = async () => {
    if (!clienteSelecionado) return;

    setSalvando(true);

    try {
      await api.put(
        `/api/v1/integracao/desativar-cliente/${clienteSelecionado.id}`
      );

      toast.success('Cliente desativado com sucesso!');
      fecharModal();
      await carregarClientes();
    } catch (error: unknown) {
      if (isAxiosError(error)) {
        const detalhe = error.response?.data?.detail;

        toast.error(
          typeof detalhe === 'string'
            ? detalhe
            : 'Não foi possível desativar o cliente.'
        );
      } else {
        toast.error('Não foi possível desativar o cliente.');
      }
    } finally {
      setSalvando(false);
    }
  };

  const ativarCliente = async (cliente: Cliente) => {
    try {
      await api.put(
        `/api/v1/integracao/ativar-cliente/${cliente.id}`
      );

      toast.success('Cliente reativado com sucesso!');
      await carregarClientes();
    } catch (error: unknown) {
      if (isAxiosError(error)) {
        const detalhe = error.response?.data?.detail;

        toast.error(
          typeof detalhe === 'string'
            ? detalhe
            : 'Não foi possível reativar o cliente.'
        );
      } else {
        toast.error('Não foi possível reativar o cliente.');
      }
    }
  };

  return (
    <div className="space-y-6">
      {/* CABEÇALHO */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-white">
            Clientes
          </h1>

          <p className="mt-1 text-sm text-surface-500 dark:text-white/60">
            Gerencie os clientes cadastrados na sua conta.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={abrirCadastro}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-brand-700"
          >
            <Plus className="h-4 w-4" />
            Novo cliente
          </button>

          <button
            onClick={carregarClientes}
            disabled={carregando}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-surface-200 px-4 py-2.5 text-sm font-medium text-surface-700 transition hover:bg-surface-50 disabled:opacity-50 dark:border-white/20 dark:text-white dark:hover:bg-white/5"
          >
            <RefreshCw
              className={`h-4 w-4 ${carregando ? 'animate-spin' : ''}`}
            />
            Atualizar
          </button>
        </div>
      </div>

      {/* TOTAL DE CLIENTES */}
      <div className="rounded-2xl border border-surface-200 bg-white p-4 dark:border-white/10 dark:bg-white/5">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 dark:bg-brand-900/30">
            <Users className="h-5 w-5 text-brand-600 dark:text-brand-300" />
          </div>

          <div>
            <p className="text-sm text-surface-500 dark:text-white/60">
              {mostrarInativos ? 'Clientes desativados' : 'Clientes ativos'}
            </p>

            <p className="text-2xl font-bold text-surface-900 dark:text-white">
              {clientesDaCategoria.length}
            </p>
          </div>
        </div>
      </div>

      {/* BUSCA E FILTRO */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />

          <input
            type="text"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar por nome, e-mail ou telefone..."
            className="w-full rounded-xl border border-surface-200 bg-white py-3 pl-10 pr-4 text-sm text-surface-900 outline-none focus:border-brand-500 dark:border-white/20 dark:bg-black dark:text-white"
          />
        </div>

        <button
          onClick={() => {
            setMostrarInativos(!mostrarInativos);
            setBusca('');
          }}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-surface-200 px-4 py-3 text-sm font-medium text-surface-700 transition hover:bg-surface-50 dark:border-white/20 dark:text-white dark:hover:bg-white/5"
        >
          {mostrarInativos ? (
            <>
              <UserCheck className="h-4 w-4" />
              Ver clientes ativos
            </>
          ) : (
            <>
              <UserX className="h-4 w-4" />
              Ver desativados
            </>
          )}
        </button>
      </div>

      {/* LISTAGEM */}
      <div className="overflow-hidden rounded-2xl border border-surface-200 bg-white dark:border-white/10 dark:bg-white/5">
        {carregando ? (
          <div className="p-10 text-center text-sm text-surface-500 dark:text-white/60">
            Carregando clientes...
          </div>
        ) : clientesFiltrados.length === 0 ? (
          <div className="p-10 text-center">
            <Users className="mx-auto mb-3 h-10 w-10 text-surface-400" />

            <h2 className="font-semibold text-surface-900 dark:text-white">
              {clientesDaCategoria.length === 0
                ? mostrarInativos
                  ? 'Nenhum cliente desativado'
                  : 'Nenhum cliente cadastrado'
                : 'Nenhum resultado encontrado'}
            </h2>

            <p className="mt-1 text-sm text-surface-500 dark:text-white/60">
              {clientesDaCategoria.length === 0
                ? mostrarInativos
                  ? 'Os clientes desativados aparecerão aqui.'
                  : 'Cadastre seu primeiro cliente para começar.'
                : 'Tente buscar por outro termo.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-surface-200 bg-surface-50 dark:border-white/10 dark:bg-white/5">
                <tr>
                  <th className="px-5 py-4 font-semibold text-surface-600 dark:text-white/70">
                    Nome
                  </th>

                  <th className="px-5 py-4 font-semibold text-surface-600 dark:text-white/70">
                    E-mail
                  </th>

                  <th className="px-5 py-4 font-semibold text-surface-600 dark:text-white/70">
                    Telefone
                  </th>

                  <th className="px-5 py-4 text-right font-semibold text-surface-600 dark:text-white/70">
                    Ações
                  </th>
                </tr>
              </thead>

              <tbody className="divide-y divide-surface-100 dark:divide-white/10">
                {clientesFiltrados.map((cliente) => (
                  <tr
                    key={cliente.id}
                    className="transition hover:bg-surface-50 dark:hover:bg-white/5"
                  >
                    <td className="whitespace-nowrap px-5 py-4 font-medium text-surface-900 dark:text-white">
                      {cliente.nome}
                    </td>

                    <td className="px-5 py-4 text-surface-600 dark:text-white/60">
                      {cliente.email || '—'}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4 text-surface-600 dark:text-white/60">
                      {cliente.telefone || '—'}
                    </td>

                    <td className="whitespace-nowrap px-5 py-4">
                      <div className="flex items-center justify-end gap-2">
                        {mostrarInativos ? (
                          <button
                            onClick={() => ativarCliente(cliente)}
                            title="Reativar cliente"
                            className="inline-flex items-center gap-2 rounded-lg bg-green-50 px-3 py-2 text-xs font-medium text-green-700 transition hover:bg-green-100 dark:bg-green-900/20 dark:text-green-300 dark:hover:bg-green-900/40"
                          >
                            <UserCheck className="h-4 w-4" />
                            Reativar
                          </button>
                        ) : (
                          <button
                            onClick={() => abrirEdicao(cliente)}
                            title="Editar cliente"
                            className="rounded-lg p-2 text-surface-500 transition hover:bg-brand-50 hover:text-brand-600 dark:text-white/60 dark:hover:bg-white/10 dark:hover:text-brand-300"
                          >
                            <Pencil className="h-4 w-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* MODAL */}
      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-lg rounded-2xl border border-surface-200 bg-white shadow-xl dark:border-white/10 dark:bg-[#171717]">
            {/* CABEÇALHO DO MODAL */}
            <div className="flex items-center justify-between border-b border-surface-200 px-6 py-4 dark:border-white/10">
              <div>
                <h2 className="text-lg font-bold text-surface-900 dark:text-white">
                  {modal === 'criar' ? 'Cadastrar cliente' : 'Editar cliente'}
                </h2>

                <p className="mt-1 text-sm text-surface-500 dark:text-white/60">
                  {modal === 'criar'
                    ? 'Preencha os dados do novo cliente.'
                    : 'Atualize as informações do cliente.'}
                </p>
              </div>

              <button
                onClick={fecharModal}
                disabled={salvando}
                className="rounded-lg p-2 text-surface-500 transition hover:bg-surface-100 dark:text-white/60 dark:hover:bg-white/10"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* FORMULÁRIO */}
            <form
              onSubmit={modal === 'criar' ? cadastrarCliente : editarCliente}
              className="space-y-4 p-6"
            >
              <div>
                <label className="mb-1.5 block text-sm font-medium text-surface-700 dark:text-white/80">
                  Nome
                </label>

                <input
                  type="text"
                  value={nome}
                  onChange={(e) => setNome(e.target.value)}
                  placeholder="Nome do cliente"
                  required
                  className="w-full rounded-xl border border-surface-200 bg-white px-4 py-3 text-sm text-surface-900 outline-none focus:border-brand-500 dark:border-white/20 dark:bg-black dark:text-white"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-surface-700 dark:text-white/80">
                  Telefone
                </label>

                <input
                  type="text"
                  value={telefone}
                  onChange={(e) => setTelefone(e.target.value)}
                  placeholder="Telefone do cliente"
                  required
                  className="w-full rounded-xl border border-surface-200 bg-white px-4 py-3 text-sm text-surface-900 outline-none focus:border-brand-500 dark:border-white/20 dark:bg-black dark:text-white"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-surface-700 dark:text-white/80">
                  E-mail
                </label>

                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="E-mail do cliente"
                  className="w-full rounded-xl border border-surface-200 bg-white px-4 py-3 text-sm text-surface-900 outline-none focus:border-brand-500 dark:border-white/20 dark:bg-black dark:text-white"
                />
              </div>

              {/* AÇÕES */}
              <div className="flex flex-col-reverse gap-2 border-t border-surface-200 pt-4 dark:border-white/10 sm:flex-row sm:items-center sm:justify-between">
                {modal === 'editar' ? (
                  <button
                    type="button"
                    onClick={desativarCliente}
                    disabled={salvando}
                    className="inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium text-red-600 transition hover:bg-red-50 disabled:opacity-50 dark:text-red-400 dark:hover:bg-red-900/20"
                  >
                    <UserX className="h-4 w-4" />
                    Desativar cliente
                  </button>
                ) : (
                  <div />
                )}

                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={fecharModal}
                    disabled={salvando}
                    className="flex-1 rounded-xl border border-surface-200 px-4 py-2.5 text-sm font-medium text-surface-700 transition hover:bg-surface-50 disabled:opacity-50 dark:border-white/20 dark:text-white dark:hover:bg-white/5 sm:flex-none"
                  >
                    Cancelar
                  </button>

                  <button
                    type="submit"
                    disabled={salvando}
                    className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-brand-700 disabled:opacity-50 sm:flex-none"
                  >
                    <Save className="h-4 w-4" />
                    {salvando
                      ? 'Salvando...'
                      : modal === 'criar'
                        ? 'Cadastrar'
                        : 'Salvar alterações'}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
