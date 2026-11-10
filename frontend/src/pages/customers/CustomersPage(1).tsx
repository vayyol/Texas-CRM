
import { useEffect, useMemo, useState } from 'react';
import { Search, Users, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { isAxiosError } from 'axios';
import { api } from '@/lib/api';

interface Cliente {
  id: number;
  nome: string;
  email?: string | null;
  telefone?: string | null;
  status?: string | null;
}

export default function CustomersPage() {
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [busca, setBusca] = useState('');
  const [carregando, setCarregando] = useState(true);

  const carregarClientes = async () => {
    setCarregando(true);

    try {
      const response = await api.get(
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

  const clientesFiltrados = useMemo(() => {
    const termo = busca.toLowerCase().trim();

    return clientes.filter((cliente) =>
      [
        cliente.nome,
        cliente.email ?? '',
        cliente.telefone ?? '',
        cliente.status ?? '',
      ].some((campo) => campo.toLowerCase().includes(termo))
    );
  }, [clientes, busca]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-white">
            Clientes
          </h1>
          <p className="mt-1 text-sm text-surface-500 dark:text-white/60">
            Consulte os clientes cadastrados na sua conta.
          </p>
        </div>

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

      <div className="rounded-2xl border border-surface-200 bg-white p-4 dark:border-white/10 dark:bg-white/5">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 dark:bg-brand-900/30">
            <Users className="h-5 w-5 text-brand-600 dark:text-brand-300" />
          </div>

          <div>
            <p className="text-sm text-surface-500 dark:text-white/60">
              Total de clientes
            </p>
            <p className="text-2xl font-bold text-surface-900 dark:text-white">
              {clientes.length}
            </p>
          </div>
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
        <input
          type="text"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder="Buscar por nome, e-mail, telefone ou status..."
          className="w-full rounded-xl border border-surface-200 bg-white py-3 pl-10 pr-4 text-sm text-surface-900 outline-none focus:border-brand-500 dark:border-white/20 dark:bg-black dark:text-white"
        />
      </div>

      <div className="overflow-hidden rounded-2xl border border-surface-200 bg-white dark:border-white/10 dark:bg-white/5">
        {carregando ? (
          <div className="p-10 text-center text-sm text-surface-500 dark:text-white/60">
            Carregando clientes...
          </div>
        ) : clientesFiltrados.length === 0 ? (
          <div className="p-10 text-center">
            <Users className="mx-auto mb-3 h-10 w-10 text-surface-400" />
            <h2 className="font-semibold text-surface-900 dark:text-white">
              {clientes.length === 0
                ? 'Nenhum cliente cadastrado'
                : 'Nenhum resultado encontrado'}
            </h2>
            <p className="mt-1 text-sm text-surface-500 dark:text-white/60">
              {clientes.length === 0
                ? 'Os clientes cadastrados pela integração aparecerão aqui.'
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
                  <th className="px-5 py-4 font-semibold text-surface-600 dark:text-white/70">
                    Status
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
                    <td className="whitespace-nowrap px-5 py-4 text-surface-600 dark:text-white/60">
                      {cliente.status || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
