import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import minimize
import matplotlib.gridspec as gridspec

# ---------------------------------------------------------
# 1. Scenario Generation (The Engine)
#    Using a Vasicek Mean-Reverting Model for Interest Rates
# ---------------------------------------------------------
class VasicekModel:
    def __init__(self, r0, kappa, theta, sigma, T, dt=1/12):
        """
        r0: Initial interest rate
        kappa: Speed of mean reversion
        theta: Long-term mean interest rate
        sigma: Volatility of interest rates
        T: Time horizon in years
        dt: Time step size (default monthly)
        """
        self.r0 = r0
        self.kappa = kappa
        self.theta = theta
        self.sigma = sigma
        self.T = T
        self.dt = dt
        self.steps = int(T / dt)
        self.times = np.linspace(0, T, self.steps + 1)

    def generate_paths(self, n_sims=1000, seed=42):
        """Simulate future short rate paths."""
        np.random.seed(seed)
        rates = np.zeros((n_sims, self.steps + 1))
        rates[:, 0] = self.r0
        
        for t in range(self.steps):
            # Euler-Maruyama discretization
            dr = self.kappa * (self.theta - rates[:, t]) * self.dt + \
                 self.sigma * np.sqrt(self.dt) * np.random.normal(size=n_sims)
            rates[:, t+1] = rates[:, t] + dr
            
        return rates

    def zero_coupon_price(self, r_t, t, T_maturity):
        """
        Calculates the Price of a Zero Coupon Bond under Vasicek dynamics.
        This ensures pricing is 'Arbitrage Free' relative to the rate model.
        P(t, T) = A(t, T) * exp(-B(t, T) * r_t)
        """
        tau = T_maturity - t
        if tau <= 0: return 1.0 # Matured

        B = (1 - np.exp(-self.kappa * tau)) / self.kappa
        A = np.exp((self.theta - self.sigma**2 / (2 * self.kappa**2)) * (B - tau) - (self.sigma**2 / (4 * self.kappa)) * B**2)
        
        return A * np.exp(-B * r_t)

# ---------------------------------------------------------
# 2. Asset & Liability Definitions
# ---------------------------------------------------------
class Liability:
    def __init__(self, cashflows, dt):
        """
        cashflows: Array of expected payouts per time step
        dt: time step size
        """
        self.cashflows = np.array(cashflows)
        self.dt = dt

    def present_value(self, rate_path, times, model):
        """
        Calculate PV of liabilities for a specific simulation path.
        PV = Sum(Cashflow_i * DiscountFactor_i)
        """
        pv = 0
        # Simplified discounting: We discount each cashflow back to t=0
        # utilizing the zero-coupon pricing logic from the model
        # corresponding to the specific time of the cashflow.
        
        for i, cf in enumerate(self.cashflows):
            if cf == 0: continue
            t_flow = times[i]
            # Price of $1 paid at t_flow, viewed from t=0 with rate r0
            # Note: In a full path dependent simulation, we might look at value at horizon.
            # Here we value at T=0.
            discount_factor = model.zero_coupon_price(rate_path[0], 0, t_flow)
            pv += cf * discount_factor
        return pv

    def terminal_value_surplus(self, rate_path, assets_terminal_value):
        """
        Compare assets at T vs accumulated liability costs.
        """
        # For simplicity in this demo, we treat liabilities as a
        # lump sum requirement at the end (Horizon) adjusted for interest rates
        pass

# ---------------------------------------------------------
# 3. The ALM System (Optimization Logic)
# ---------------------------------------------------------
class ALMSystem:
    def __init__(self, model, initial_wealth):
        self.model = model
        self.initial_wealth = initial_wealth
        self.assets = {
            'Cash': {'maturity': 0.25},      # 3-month bills
            'Bond_5Y': {'maturity': 5.0},    # 5-Year Note
            'Bond_10Y': {'maturity': 10.0},  # 10-Year Bond
            'Bond_30Y': {'maturity': 30.0}   # 30-Year Bond
        }
        
    def simulate_horizon_returns(self, rate_paths, horizon_step):
        """
        Calculate the return of each asset class at the Investment Horizon.
        """
        n_sims = rate_paths.shape[0]
        asset_returns = pd.DataFrame(index=range(n_sims))
        
        t_horizon = self.model.times[horizon_step]
        r_0 = rate_paths[:, 0]           # Rate at t=0
        r_H = rate_paths[:, horizon_step] # Rate at Horizon
        
        for name, specs in self.assets.items():
            mat = specs['maturity']
            
            # Price at t=0
            p0 = self.model.zero_coupon_price(r_0, 0, mat)
            
            # Price at t=Horizon
            # Bond has aged: Time to maturity is now (mat - t_horizon)
            # If matured, value is 1.0 (assuming Face Value $1)
            pH = np.array([self.model.zero_coupon_price(r, 0, mat - t_horizon) 
                           for r in r_H])
            
            # Simple return calculation
            asset_returns[name] = (pH - p0) / p0
            
        return asset_returns

    def optimize_portfolio(self, asset_returns, liabilities_pv, risk_aversion=0.5):
        """
        Objective: Maximize Utility = E[Surplus] - lambda * Std[Surplus]
        Constraints: Weights sum to 1, 0 <= weight <= 1
        """
        n_assets = len(self.assets)
        initial_guess = np.array([1/n_assets] * n_assets)
        
        # Target: Surplus = (Wealth * (1 + Portfolio_Ret)) - Liability_PV
        # We approximate Liability Growth or assume fixed PV for this simpler step
        
        def utility(weights):
            # Portfolio Return for every simulation
            port_ret = np.dot(asset_returns.values, weights)
            
            # Terminal Wealth
            term_wealth = self.initial_wealth * (1 + port_ret)
            
            # Surplus (simplified: Wealth - Liability Target)
            surplus = term_wealth - liabilities_pv
            
            expected_surplus = np.mean(surplus)
            risk_surplus = np.std(surplus)
            
            # Negative because we want to Minimize (-Utility)
            return -(expected_surplus - risk_aversion * risk_surplus)

        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
        bounds = tuple((0, 1) for _ in range(n_assets))
        
        result = minimize(utility, initial_guess, method='SLSQP', 
                          bounds=bounds, constraints=constraints)
        
        return result.x

# ---------------------------------------------------------
# 4. Main Execution
# ---------------------------------------------------------
def run_alm_demo():
    print("--- Initializing ALM System ---")
    
    # 1. Setup Economic Environment (Vasicek Model)
    # r0=5%, Mean Reversion Speed=0.3, LongTerm=5%, Vol=2%
    model = VasicekModel(r0=0.05, kappa=0.3, theta=0.05, sigma=0.02, T=10.0)
    
    # 2. Generate Scenarios
    print("Generating 2000 Interest Rate Scenarios...")
    paths = model.generate_paths(n_sims=2000)
    
    # 3. Define Liability Stream (e.g., Expected Payouts over 10 years)
    # A liability profile that increases then decreases
    steps = model.steps + 1
    liab_schedule = np.zeros(steps)
    # Heavy payouts in year 5 (step 60)
    liab_schedule[60] = 500_000 
    # Heavy payouts in year 10 (step 120)
    liab_schedule[120] = 500_000
    
    liability = Liability(liab_schedule, model.dt)
    # Approximate PV of Liability to cover
    # We use the mean path for a baseline PV estimate
    mean_path = np.mean(paths, axis=0)
    target_liability_pv = liability.present_value(mean_path, model.times, model)
    print(f"Present Value of Liabilities: ${target_liability_pv:,.2f}")
    
    # 4. Initialize ALM System with Current Wealth
    # Assume we are currently underfunded (90% funded)
    current_wealth = target_liability_pv * 0.90
    alm = ALMSystem(model, current_wealth)
    
    # 5. Optimize for a 1-Year Rebalancing Horizon
    # We look 1 year ahead (step 12) to optimize our mix
    print("Calculating Asset Returns at 1-Year Horizon...")
    horizon_step = 12 
    asset_returns = alm.simulate_horizon_returns(paths, horizon_step)
    
    print("Optimizing Portfolio Allocations...")
    # Higher lambda = More conservative (hates volatility)
    opt_weights = alm.optimize_portfolio(asset_returns, target_liability_pv, risk_aversion=2.0)
    
    # ---------------------------------------------------------
    # 5. Visualizations
    # ---------------------------------------------------------
    fig = plt.figure(figsize=(14, 8))
    gs = gridspec.GridSpec(2, 2)
    
    # Plot 1: Interest Rate Scenarios
    ax1 = plt.subplot(gs[0, 0])
    ax1.plot(model.times, paths[:50].T, alpha=0.3, color='blue')
    ax1.plot(model.times, np.mean(paths, axis=0), 'r--', linewidth=2, label='Mean Path')
    ax1.set_title('Vasicek Interest Rate Scenarios (First 50)')
    ax1.set_ylabel('Interest Rate')
    ax1.set_xlabel('Time (Years)')
    ax1.legend()
    
    # Plot 2: Asset Allocation Result
    ax2 = plt.subplot(gs[0, 1])
    asset_names = list(alm.assets.keys())
    bars = ax2.bar(asset_names, opt_weights, color=['green', 'skyblue', 'orange', 'purple'])
    ax2.set_title('Optimal Asset Allocation')
    ax2.set_ylim(0, 1.1)
    for bar in bars:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                 f'{height:.1%}', ha='center', va='bottom')
        
    # Plot 3: Distribution of Surplus at Horizon (Unoptimized vs Optimized)
    ax3 = plt.subplot(gs[1, :])
    
    # Calculate distribution if we held 100% Cash
    cash_returns = asset_returns['Cash']
    cash_wealth = current_wealth * (1 + cash_returns)
    cash_surplus = cash_wealth - target_liability_pv
    
    # Calculate distribution for Optimized Portfolio
    opt_returns = np.dot(asset_returns.values, opt_weights)
    opt_wealth = current_wealth * (1 + opt_returns)
    opt_surplus = opt_wealth - target_liability_pv
    
    ax3.hist(cash_surplus, bins=50, alpha=0.5, label='100% Cash Strategy', color='gray')
    ax3.hist(opt_surplus, bins=50, alpha=0.6, label='Optimized ALM Strategy', color='green')
    ax3.axvline(0, color='red', linestyle='--', label='Fully Funded Threshold')
    ax3.set_title('Distribution of Funding Surplus at 1-Year Horizon')
    ax3.set_xlabel('Surplus / Deficit ($)')
    ax3.legend()
    
    plt.tight_layout()
    plt.savefig('alm_dashboard.png')
    print("Optimization Complete. Dashboard generated.")

if __name__ == "__main__":
    run_alm_demo()