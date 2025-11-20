import asyncio
import json
from axp_client import AxpClient

async def main():
    client = AxpClient()
    await client.start_token_refresh()

    print("Welcome to the Avaya AXP Audit Trail Analyzer!")

    while True:
        print("\nWhat would you like to do?")
        print("1. Get a new bearer token")
        print("2. Get user updates")
        print("3. Fetch and store queues")
        print("4. Show stored queues")
        print("5. Show token status")
        print("6. Exit")

        choice = input("Enter your choice (1-6): ")

        if choice == "1":
            token = await client.get_bearer_token()
            if token:
                print(f"Bearer Token: {token[:10]}...")
            else:
                print("Failed to get a new bearer token.")
        elif choice == "2":
            print("Getting user updates...")
            user_updates = await client.get_user_updates()
            if user_updates:
                print("User Updates:")
                print(json.dumps(user_updates, indent=2))
            else:
                print("Failed to get user updates.")
        elif choice == "3":
            print("Fetching and storing queues...")
            await client.get_queues()
        elif choice == "4":
            print("Stored Queues:")
            if client.queues:
                print(json.dumps(client.queues, indent=2))
            else:
                print("No queues stored. Please fetch them first.")
        elif choice == "5":
            status = client.get_token_expiration_status()
            print("Token Status:")
            print(f"  Access token expires in: {status['access_token_remaining']:.2f} seconds")
            print(f"  Refresh token expires in: {status['refresh_token_remaining']:.2f} seconds")
        elif choice == "6":
            break
        else:
            print("Invalid choice. Please try again.")

    await client.stop_token_refresh()
    print("Goodbye!")

if __name__ == "__main__":
    asyncio.run(main())
