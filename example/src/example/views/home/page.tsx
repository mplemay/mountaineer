const Home = () => {
  return (
    <div className="p-6">
      <h1 className="text-2xl">Mountaineer V2 Example</h1>
      <p className="text-green-500">Welcome to the home page</p>
      <p>
        <a className="font-medium text-blue-500" href="/detail/test-123">
          Go to Detail Page
        </a>
      </p>
    </div>
  );
};

export default Home;
