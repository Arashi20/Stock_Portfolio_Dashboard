#Simple 2-stage DCF calculator
def dcf_valuation(initial_fcf, growth_rate_1_5, growth_rate_6_10, discount_rate, terminal_growth_rate, shares_outstanding):
    # Projected FCFs for the next 10 years

    # Convert percentage inputs to decimals
    growth_rate_1_5 /= 100
    growth_rate_6_10 /= 100
    discount_rate /= 100
    terminal_growth_rate /= 100

    if discount_rate <= terminal_growth_rate:
        raise ValueError("Discount rate must be greater than terminal growth rate.")

    if shares_outstanding <= 0:
        raise ValueError("Shares outstanding must be a positive number.")

    fcfs = []
    for year in range(1, 11):
        if year <= 5:
            fcf = initial_fcf * (1 + growth_rate_1_5) ** year
        else:
            fcf = fcfs[4] * (1 + growth_rate_6_10) ** (year - 5)
        fcfs.append(fcf)
    
    # Discount each FCF to present value
    discounted_fcfs = [fcf / ((1 + discount_rate) ** year) for year, fcf in zip(range(1, 11), fcfs)]
    
    # Calculate the terminal value at year 10
    terminal_value = fcfs[-1] * (1 + terminal_growth_rate) / (discount_rate - terminal_growth_rate)
    discounted_terminal_value = terminal_value / ((1 + discount_rate) ** 10)
    
    # Calculate enterprise value and intrinsic value per share
    enterprise_value = sum(discounted_fcfs) + discounted_terminal_value
    intrinsic_value_per_share = enterprise_value / shares_outstanding
    
    return intrinsic_value_per_share


