import { useState, useEffect } from 'react';
import { supabase } from '../lib/supabase';
import { InstagramAccount } from '../types';

export function Dashboard() {
  const [accounts, setAccounts] = useState<InstagramAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState<string | null>(null);

  useEffect(() => {
    fetchAccounts();
  }, []);

  const fetchAccounts = async () => {
    try {
      const { data, error } = await supabase
        .from('instagram_accounts')
        .select('*')
        .eq('is_active', true)
        .order('created_at', { ascending: false });

      if (error) throw error;
      setAccounts(data || []);
    } catch (error) {
      console.error('Error fetching accounts:', error);
    } finally {
      setLoading(false);
    }
  };

  const refreshAccount = async (accountId: string) => {
    setRefreshing(accountId);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error('Not authenticated');

      const response = await fetch(
        `${import.meta.env.VITE_SUPABASE_URL}/functions/v1/instagram-status`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ account_id: accountId }),
        }
      );

      if (!response.ok) throw new Error('Failed to refresh account');
      await fetchAccounts();
    } catch (error) {
      console.error('Error refreshing account:', error);
    } finally {
      setRefreshing(null);
    }
  };

  const handleSignOut = async () => {
    await supabase.auth.signOut();
  };

  const connectInstagram = async () => {
    try {
      const response = await fetch(
        `${import.meta.env.VITE_SUPABASE_URL}/functions/v1/instagram-oauth/auth-url`
      );
      const data = await response.json();
      window.open(data.auth_url, '_blank');
    } catch (error) {
      console.error('Error getting auth URL:', error);
    }
  };

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f9fafb'
      }}>
        <div style={{ fontSize: '18px', color: '#6b7280' }}>Loading...</div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f9fafb' }}>
      <nav style={{
        background: 'white',
        borderBottom: '1px solid #e5e7eb',
        padding: '16px 24px'
      }}>
        <div style={{
          maxWidth: '1200px',
          margin: '0 auto',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <h1 style={{
            fontSize: '24px',
            fontWeight: 'bold',
            color: '#1f2937'
          }}>
            Instagram Business Manager
          </h1>
          <button
            onClick={handleSignOut}
            style={{
              padding: '8px 16px',
              background: 'transparent',
              color: '#6b7280',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              fontSize: '14px',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#f3f4f6';
              e.currentTarget.style.color = '#374151';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.color = '#6b7280';
            }}
          >
            Sign Out
          </button>
        </div>
      </nav>

      <main style={{
        maxWidth: '1200px',
        margin: '0 auto',
        padding: '32px 24px'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '24px'
        }}>
          <h2 style={{
            fontSize: '20px',
            fontWeight: '600',
            color: '#111827'
          }}>
            Connected Accounts
          </h2>
          <button
            onClick={connectInstagram}
            style={{
              padding: '10px 20px',
              background: '#667eea',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              fontSize: '14px',
              fontWeight: '500',
              cursor: 'pointer',
              transition: 'background-color 0.2s'
            }}
            onMouseEnter={(e) => e.currentTarget.style.background = '#5568d3'}
            onMouseLeave={(e) => e.currentTarget.style.background = '#667eea'}
          >
            + Connect Account
          </button>
        </div>

        {accounts.length === 0 ? (
          <div style={{
            background: 'white',
            borderRadius: '8px',
            padding: '48px',
            textAlign: 'center',
            border: '1px solid #e5e7eb'
          }}>
            <div style={{
              fontSize: '48px',
              marginBottom: '16px'
            }}>
              📱
            </div>
            <h3 style={{
              fontSize: '18px',
              fontWeight: '600',
              color: '#111827',
              marginBottom: '8px'
            }}>
              No Instagram accounts connected
            </h3>
            <p style={{
              color: '#6b7280',
              marginBottom: '24px',
              fontSize: '14px'
            }}>
              Connect your Instagram Business account to get started
            </p>
            <button
              onClick={connectInstagram}
              style={{
                padding: '10px 20px',
                background: '#667eea',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                fontSize: '14px',
                fontWeight: '500',
                cursor: 'pointer',
                transition: 'background-color 0.2s'
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = '#5568d3'}
              onMouseLeave={(e) => e.currentTarget.style.background = '#667eea'}
            >
              Connect Instagram Account
            </button>
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
            gap: '24px'
          }}>
            {accounts.map((account) => (
              <div
                key={account.id}
                style={{
                  background: 'white',
                  borderRadius: '8px',
                  padding: '24px',
                  border: '1px solid #e5e7eb',
                  transition: 'box-shadow 0.2s'
                }}
                onMouseEnter={(e) => e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)'}
                onMouseLeave={(e) => e.currentTarget.style.boxShadow = 'none'}
              >
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  marginBottom: '16px'
                }}>
                  {account.profile_picture_url ? (
                    <img
                      src={account.profile_picture_url}
                      alt={account.username}
                      style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '50%',
                        marginRight: '12px'
                      }}
                    />
                  ) : (
                    <div style={{
                      width: '48px',
                      height: '48px',
                      borderRadius: '50%',
                      background: '#667eea',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'white',
                      fontSize: '20px',
                      fontWeight: 'bold',
                      marginRight: '12px'
                    }}>
                      {account.username[0].toUpperCase()}
                    </div>
                  )}
                  <div>
                    <h3 style={{
                      fontSize: '16px',
                      fontWeight: '600',
                      color: '#111827',
                      marginBottom: '4px'
                    }}>
                      @{account.username}
                    </h3>
                    <span style={{
                      fontSize: '12px',
                      color: '#6b7280',
                      textTransform: 'uppercase'
                    }}>
                      {account.account_type}
                    </span>
                  </div>
                </div>

                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: '12px',
                  marginBottom: '16px'
                }}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{
                      fontSize: '20px',
                      fontWeight: 'bold',
                      color: '#111827'
                    }}>
                      {account.followers_count.toLocaleString()}
                    </div>
                    <div style={{
                      fontSize: '12px',
                      color: '#6b7280'
                    }}>
                      Followers
                    </div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{
                      fontSize: '20px',
                      fontWeight: 'bold',
                      color: '#111827'
                    }}>
                      {account.follows_count.toLocaleString()}
                    </div>
                    <div style={{
                      fontSize: '12px',
                      color: '#6b7280'
                    }}>
                      Following
                    </div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{
                      fontSize: '20px',
                      fontWeight: 'bold',
                      color: '#111827'
                    }}>
                      {account.media_count.toLocaleString()}
                    </div>
                    <div style={{
                      fontSize: '12px',
                      color: '#6b7280'
                    }}>
                      Posts
                    </div>
                  </div>
                </div>

                <div style={{
                  fontSize: '12px',
                  color: '#9ca3af',
                  marginBottom: '16px'
                }}>
                  Last synced: {new Date(account.last_sync_at).toLocaleString()}
                </div>

                <button
                  onClick={() => refreshAccount(account.id)}
                  disabled={refreshing === account.id}
                  style={{
                    width: '100%',
                    padding: '10px',
                    background: refreshing === account.id ? '#e5e7eb' : '#f3f4f6',
                    color: refreshing === account.id ? '#9ca3af' : '#374151',
                    border: 'none',
                    borderRadius: '6px',
                    fontSize: '14px',
                    fontWeight: '500',
                    cursor: refreshing === account.id ? 'not-allowed' : 'pointer',
                    transition: 'background-color 0.2s'
                  }}
                  onMouseEnter={(e) => {
                    if (refreshing !== account.id) {
                      e.currentTarget.style.background = '#e5e7eb';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (refreshing !== account.id) {
                      e.currentTarget.style.background = '#f3f4f6';
                    }
                  }}
                >
                  {refreshing === account.id ? 'Refreshing...' : 'Refresh Status'}
                </button>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
